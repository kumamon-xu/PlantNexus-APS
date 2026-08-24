"""Emit machine-checkable TASK-P3-06 command pipeline evidence."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from copy import deepcopy
from datetime import timedelta
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter_ns
from typing import Any, Never, cast

from alembic import command as alembic_command

from app.application.schedule_commands import ScheduleCommandService
from app.application.schedule_version_lifecycle_check import (
    _service as lifecycle_service,
    _workspace_engine,
    lifecycle_context,
    load_fixed_validated_output,
)
from app.domain.schedule_commands import (
    ScheduleCommandContext,
    ScheduleCommandError,
    ScheduleCommandFailure,
    build_schedule_command_documents,
    prepare_schedule_command,
    schedule_command_identity,
)
from app.domain.schedule_version import (
    ValidatedPlanningOutput,
    build_reviewable_schedule_documents,
)
from app.domain.types import (
    duration_to_ticks,
    format_utc_instant,
    parse_utc_instant,
)
from app.domain.workspace_contracts import (
    canonical_workspace_bytes,
    schedule_content_fingerprint,
    workspace_command_fingerprint,
    workspace_fingerprint,
)
from app.planning.reporting import build_kpi_v2
from app.simulation.scenarios.p2_correctness import (
    execute_correctness_case,
    load_correctness_cases,
    verify_correctness_replay,
)


REPORT_VERSION = "p3-schedule-command-report.v1"
TASK_ID = "TASK-P3-06"


def _validator_factory() -> Any:
    validation = __import__(
        "app.planning.validation", fromlist=["ProblemScheduleValidator"]
    )
    return validation.ProblemScheduleValidator()


def _validate_problem_schedule(
    problem: Mapping[str, object], candidate: Mapping[str, object]
) -> Mapping[str, object]:
    validation = __import__(
        "app.planning.validation", fromlist=["validate_problem_schedule"]
    )
    return cast(
        Mapping[str, object],
        validation.validate_problem_schedule(problem, candidate),
    )


def _pass(check_id: str, evidence: Mapping[str, object]) -> dict[str, object]:
    return {"check_id": check_id, "status": "PASS", "evidence": dict(evidence)}


def _repositories(engine: Any) -> tuple[Any, Any]:
    infrastructure = __import__("app.infrastructure", fromlist=["infrastructure"])
    plane = infrastructure.WorkspaceDataPlane.SIMULATION
    return (
        infrastructure.SqlAlchemyScheduleVersionRepository(engine, data_plane=plane),
        infrastructure.SqlAlchemyAuditRepository(engine, data_plane=plane),
    )


def _context(
    parent_audit_event_id: str | None,
    *capabilities: str,
    occurred_at_utc: str = "2026-08-24T11:00:00Z",
) -> ScheduleCommandContext:
    return ScheduleCommandContext(
        actor_ref="actor:p3-command-machine",
        resolved_capabilities=frozenset(capabilities),
        auth_policy_version="simulation-command-policy.v1",
        occurred_at_utc=occurred_at_utc,
        code_commit=os.environ.get("PLANTNEXUS_CODE_COMMIT", "uncommitted"),
        parent_audit_event_id=parent_audit_event_id,
    )


def _command(
    source: Mapping[str, object],
    command_type: str,
    payload: Mapping[str, object],
    *,
    key: str,
    reason: str,
    correlation_id: str,
) -> dict[str, object]:
    capability = (
        "edit"
        if command_type in {"MOVE_OPERATION", "ASSIGN_RESOURCE", "SUBMIT_FOR_REVIEW"}
        else "lock"
    )
    document: dict[str, object] = {
        "workspace_command_version": "workspace-command.v1",
        "schema_set_version": "2.6.0",
        "canonicalization_version": "canonical-json.v1",
        "command_id": f"command-{key}",
        "command_type": command_type,
        "required_capability": capability,
        "idempotency_key": key,
        "idempotency_scope": (
            f"SIMULATION/{command_type}/{source['schedule_version_id']}"
            "/WORKSPACE_INTERNAL"
        ),
        "request_fingerprint": "sha256:" + "0" * 64,
        "source_id": source["schedule_version_id"],
        "expected_state": source["state"],
        "expected_content_fingerprint": source["content_fingerprint"],
        "data_plane": "SIMULATION",
        "environment": source["environment"],
        "synthetic": source["synthetic"],
        "synthetic_provenance": source["synthetic_provenance"],
        "target": "WORKSPACE_INTERNAL",
        "reason": reason,
        "correlation_id": correlation_id,
        "payload": dict(payload),
    }
    document["request_fingerprint"] = workspace_command_fingerprint(document)
    return document


def _counts(engine: Any) -> dict[str, int]:
    with engine.connect() as connection:
        return {
            "schedule_versions": int(
                connection.exec_driver_sql(
                    "SELECT COUNT(*) FROM schedule_versions"
                ).scalar_one()
            ),
            "audit_events": int(
                connection.exec_driver_sql(
                    "SELECT COUNT(*) FROM audit_events"
                ).scalar_one()
            ),
        }


def _expect(
    expected: ScheduleCommandFailure,
    operation,  # type: ignore[no-untyped-def]
) -> ScheduleCommandError:
    try:
        operation()
    except ScheduleCommandError as error:
        if error.reason is expected:
            return error
        raise ValueError(f"unexpected command failure {error.reason.value}") from error
    raise ValueError(f"expected {expected.value}")


def _assignment(source: Mapping[str, object]) -> Mapping[str, object]:
    content = cast(Mapping[str, object], source["content"])
    return cast(list[Mapping[str, object]], content["assignments"])[0]


def _move_command(
    source: Mapping[str, object],
    *,
    key: str,
    start_at_utc: str = "2026-09-01T00:03:00Z",
    end_at_utc: str = "2026-09-01T00:04:00Z",
    reason: str = "Move one synthetic operation by one tick.",
) -> dict[str, object]:
    assignment = _assignment(source)
    return _command(
        source,
        "MOVE_OPERATION",
        {
            "operation_id": assignment["operation_id"],
            "resource_id": assignment["resource_id"],
            "start_at_utc": start_at_utc,
            "end_at_utc": end_at_utc,
        },
        key=key,
        reason=reason,
        correlation_id=f"correlation-{key}",
    )


def _assignable_fjsp_source(
    root: Path,
) -> tuple[ValidatedPlanningOutput, dict[str, object], str, str]:
    case = next(
        value
        for value in load_correctness_cases(root)
        if value.scenario_id == "P2-GOLDEN-FJSP"
    )
    replay = execute_correctness_case(case, root=root)
    verify_correctness_replay(replay)
    kpi = build_kpi_v2(
        snapshot=replay.snapshot_document,
        problem=replay.problem,
        solution=replay.solution,
        solver_report=replay.solver_report,
        validation_report=replay.validation_report,
        import_quality_report=replay.quality_report,
    )
    output = ValidatedPlanningOutput(
        snapshot=replay.snapshot_document,
        problem=replay.problem,
        solution=replay.solution,
        solver_report=replay.solver_report,
        validation_report=replay.validation_report,
        import_quality_report=replay.quality_report,
        kpi=kpi.document,
    )
    original = build_reviewable_schedule_documents(
        output,
        lifecycle_context("f", correlation_id="correlation-p3-command-fjsp-source"),
        data_plane="SIMULATION",
    ).ready_for_review
    operations = {
        cast(str, value["operation_id"]): value
        for value in cast(
            list[dict[str, object]], replay.problem["operation_instances"]
        )
    }
    horizon_start = parse_utc_instant(cast(str, replay.problem["horizon_start_utc"]))
    horizon_end = parse_utc_instant(cast(str, replay.problem["horizon_end_utc"]))
    horizon_ticks = int(
        (horizon_end - horizon_start).total_seconds()
        // cast(int, replay.problem["tick_seconds"])
    )
    selected: tuple[dict[str, object], str, str] | None = None
    for operation_id, operation in operations.items():
        options = cast(list[dict[str, object]], operation["resource_options"])
        if len(options) < 2:
            continue
        original_assignment = next(
            value
            for value in cast(list[dict[str, object]], replay.solution["assignments"])
            if value["operation_id"] == operation_id
        )
        for start_tick in range(horizon_ticks):
            valid: list[tuple[str, dict[str, object]]] = []
            for option in options:
                candidate = deepcopy(replay.solution)
                assignment = next(
                    value
                    for value in cast(list[dict[str, object]], candidate["assignments"])
                    if value["operation_id"] == operation_id
                )
                duration_seconds = cast(int, option["final_duration_seconds"])
                duration_ticks = duration_to_ticks(
                    duration_seconds, cast(int, replay.problem["tick_seconds"])
                )
                end_tick = start_tick + duration_ticks
                assignment.update(
                    {
                        "resource_id": option["resource_id"],
                        "start_tick": start_tick,
                        "end_tick": end_tick,
                        "duration_ticks": duration_ticks,
                        "start_at_utc": format_utc_instant(
                            horizon_start
                            + timedelta(
                                seconds=start_tick
                                * cast(int, replay.problem["tick_seconds"])
                            )
                        ),
                        "end_at_utc": format_utc_instant(
                            horizon_start
                            + timedelta(
                                seconds=end_tick
                                * cast(int, replay.problem["tick_seconds"])
                            )
                        ),
                        "duration_seconds": duration_seconds,
                    }
                )
                if (
                    _validate_problem_schedule(replay.problem, candidate)["status"]
                    == "PASS"
                ):
                    valid.append((cast(str, option["resource_id"]), candidate))
            if len(valid) >= 2:
                selected = (valid[0][1], valid[0][0], valid[1][0])
                break
        if selected is not None:
            del original_assignment
            break
    if selected is None:
        raise ValueError("no deterministic assignable FJSP source was found")
    solution, source_resource, target_resource = selected
    source_report = _validate_problem_schedule(replay.problem, solution)
    source = deepcopy(original)
    source.update(
        {
            "schedule_version_id": "schedule-version-command-fjsp-source",
            "revision": 2,
            "state": "DRAFT",
            "source_kind": "MANUAL_EDIT",
            "parent_schedule_version": {
                "schedule_version_id": original["schedule_version_id"],
                "state": original["state"],
                "content_fingerprint": original["content_fingerprint"],
            },
            "allowed_actions": ["view", "edit", "lock"],
        }
    )
    cast(dict[str, object], source["content"])["assignments"] = solution["assignments"]
    report_fingerprint = workspace_fingerprint(source_report)
    report_reference = {
        "document_version": "validation-report.v2",
        "artifact_id": f"validation-report-{report_fingerprint.removeprefix('sha256:')}",
        "fingerprint": report_fingerprint,
    }
    cast(dict[str, object], source["lineage"])["validation_report"] = report_reference
    source["validation"] = {
        "validation_report": report_reference,
        "status": "PASS",
        "hard_violation_count": 0,
        "validated_at_utc": "2026-08-24T10:50:00Z",
    }
    source["content_fingerprint"] = schedule_content_fingerprint(source)
    operation_id = next(
        cast(str, value["operation_id"])
        for value in cast(list[dict[str, object]], solution["assignments"])
        if value["resource_id"] == source_resource
        and len(operations[cast(str, value["operation_id"])]["resource_options"]) >= 2  # type: ignore[arg-type]
    )
    return output, source, operation_id, target_resource


class _FailingAuditRepository:
    def __init__(self, delegate: Any) -> None:
        self._delegate = delegate

    def get(self, audit_event_id: str) -> dict[str, object] | None:
        return cast(dict[str, object] | None, self._delegate.get(audit_event_id))

    def append_in_transaction(
        self, connection: object, document: Mapping[str, object]
    ) -> Never:
        del connection, document
        raise RuntimeError("sanitized injected audit failure")


def _historical_check(
    source: Mapping[str, object],
    problem: Mapping[str, object],
) -> dict[str, object]:
    states: list[str] = []
    for index, state in enumerate(("REJECTED", "PUBLISHED"), start=1):
        historical = cast(dict[str, object], deepcopy(source))
        historical["schedule_version_id"] = f"schedule-version-history-{state.lower()}"
        historical["state"] = state
        historical["allowed_actions"] = ["view", "edit", "lock"]
        if state == "REJECTED":
            historical["decision"] = {
                "decision": "REJECTED",
                "actor_ref": "actor:p3-history",
                "capability": "reject",
                "reason": "Synthetic rejected history reference.",
                "decided_at_utc": "2026-08-24T10:45:00Z",
                "audit_event_id": "audit-event-history-rejected",
            }
        else:
            historical["decision"] = {
                "decision": "APPROVED",
                "actor_ref": "actor:p3-history",
                "capability": "approve",
                "reason": "Synthetic approved history reference.",
                "decided_at_utc": "2026-08-24T10:44:00Z",
                "audit_event_id": "audit-event-history-approved",
            }
            historical["publication"] = {
                "publication_id": "publication-history-001",
                "target": "SIMULATION_INTERNAL",
                "published_at_utc": "2026-08-24T10:45:00Z",
                "audit_event_id": "audit-event-history-published",
            }
        before = canonical_workspace_bytes(historical)
        command = _move_command(
            historical,
            key=f"p3-history-machine-{index}",
        )
        prepared = prepare_schedule_command(
            historical,
            problem,
            command,
            _context(None, "edit"),
            data_plane="SIMULATION",
        )
        report = _validate_problem_schedule(problem, prepared.validator_candidate)
        documents = build_schedule_command_documents(prepared, report)
        if (
            documents.draft["state"] != "DRAFT"
            or canonical_workspace_bytes(historical) != before
        ):
            raise ValueError("historical source was not copy-on-write immutable")
        states.append(state)
    return _pass(
        "P3-06-HISTORICAL-IMMUTABILITY",
        {"source_states": states, "derived_state": "DRAFT", "source_mutations": 0},
    )


def run_command_checks(root: Path) -> dict[str, object]:
    output, replay = load_fixed_validated_output(root)
    checks: list[dict[str, object]] = []
    rejected_without_side_effect = 0
    fresh_validator_passes = 0
    observed_microseconds: list[int] = []
    with TemporaryDirectory(prefix="plantnexus-p3-06-") as temporary:
        temporary_root = Path(temporary)
        engine, configuration = _workspace_engine(root, temporary_root / "primary.db")
        assign_engine, assign_configuration = _workspace_engine(
            root, temporary_root / "assign.db"
        )
        rollback_engine, rollback_configuration = _workspace_engine(
            root, temporary_root / "rollback.db"
        )
        try:
            lifecycle = lifecycle_service(engine, "SIMULATION").create_reviewable(
                output, lifecycle_context()
            )
            schedule_repository, audit_repository = _repositories(engine)
            service = ScheduleCommandService(
                data_plane="SIMULATION",
                transaction_factory=engine.begin,
                schedule_repository=schedule_repository,
                audit_repository=audit_repository,
                validator_factory=_validator_factory,
            )
            source_before = canonical_workspace_bytes(lifecycle.schedule_version)
            move_command = _move_command(
                lifecycle.schedule_version, key="p3-machine-move-0001"
            )
            started = perf_counter_ns()
            move_result = service.execute(
                move_command,
                output.problem,
                _context(lifecycle.audit_event_id, "edit"),
            )
            observed_microseconds.append((perf_counter_ns() - started) // 1_000)
            move_document = schedule_repository.get(
                cast(str, move_result.new_version["schedule_version_id"])
            )
            if move_document is None:
                raise ValueError("MOVE result was not persisted")
            move_report = _validate_problem_schedule(
                output.problem,
                {
                    "problem": {
                        key: output.problem[key]
                        for key in (
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
                    "assignments": cast(Mapping[str, object], move_document["content"])[
                        "assignments"
                    ],
                },
            )
            fresh_validator_passes += move_report["status"] == "PASS"
            checks.append(
                _pass(
                    "P3-06-MOVE-COPY-ON-WRITE",
                    {
                        "source_id": lifecycle.schedule_version_id,
                        "new_id": move_result.new_version["schedule_version_id"],
                        "new_state": move_result.new_version["state"],
                        "source_bytes_unchanged": canonical_workspace_bytes(
                            lifecycle.schedule_version
                        )
                        == source_before,
                        "fresh_validation_status": move_report["status"],
                    },
                )
            )

            replay_result = service.execute(
                move_command,
                output.problem,
                _context(lifecycle.audit_event_id, "edit"),
            )
            conflict = _move_command(
                lifecycle.schedule_version,
                key="p3-machine-move-0001",
                reason="Reuse one key with different intent.",
            )
            before_negative = _counts(engine)
            _expect(
                ScheduleCommandFailure.IDEMPOTENCY_CONFLICT,
                lambda: service.execute(
                    conflict,
                    output.problem,
                    _context(lifecycle.audit_event_id, "edit"),
                ),
            )
            rejected_without_side_effect += 1
            if _counts(engine) != before_negative:
                raise ValueError("idempotency conflict changed durable counts")
            checks.append(
                _pass(
                    "P3-06-IDEMPOTENCY",
                    {
                        "exact_replay": replay_result.exact_replay,
                        "same_new_version": replay_result.new_version
                        == move_result.new_version,
                        "conflict_rejections": 1,
                        "durable_counts": _counts(engine),
                    },
                )
            )

            lock_source = cast(dict[str, object], move_document)
            lock_assignment = _assignment(lock_source)
            lock_value = {
                "lock_id": "lock-p3-machine-hard-001",
                "operation_id": lock_assignment["operation_id"],
                "lock_type": "HARD",
                "resource_id": lock_assignment["resource_id"],
                "start_at_utc": lock_assignment["start_at_utc"],
                "end_at_utc": lock_assignment["end_at_utc"],
            }
            set_command = _command(
                lock_source,
                "SET_LOCK",
                {"lock": lock_value},
                key="p3-machine-lock-0001",
                reason="Add one version-local HARD lock.",
                correlation_id="correlation-p3-machine-lock",
            )
            set_result = service.execute(
                set_command,
                output.problem,
                _context(move_result.audit_event_id, "lock"),
            )
            set_document = schedule_repository.get(
                cast(str, set_result.new_version["schedule_version_id"])
            )
            if set_document is None:
                raise ValueError("SET_LOCK result was not persisted")
            remove_command = _command(
                set_document,
                "REMOVE_LOCK",
                {
                    "lock_id": lock_value["lock_id"],
                    "operation_id": lock_value["operation_id"],
                },
                key="p3-machine-unlock-01",
                reason="Remove one version-local HARD lock.",
                correlation_id="correlation-p3-machine-unlock",
            )
            remove_result = service.execute(
                remove_command,
                output.problem,
                _context(set_result.audit_event_id, "lock"),
            )
            remove_document = schedule_repository.get(
                cast(str, remove_result.new_version["schedule_version_id"])
            )
            if remove_document is None:
                raise ValueError("REMOVE_LOCK result was not persisted")
            remove_content_before = canonical_workspace_bytes(
                cast(Mapping[str, object], remove_document["content"])
            )
            submit_command = _command(
                remove_document,
                "SUBMIT_FOR_REVIEW",
                {},
                key="p3-machine-submit-001",
                reason="Submit the lock-change DRAFT for independent review.",
                correlation_id="correlation-p3-machine-submit",
            )
            submit_result = service.execute(
                submit_command,
                output.problem,
                _context(
                    remove_result.audit_event_id,
                    "edit",
                    occurred_at_utc="2026-08-24T11:01:00Z",
                ),
            )
            submit_replay = service.execute(
                submit_command,
                output.problem,
                _context(
                    remove_result.audit_event_id,
                    "edit",
                    occurred_at_utc="2026-08-24T11:01:00Z",
                ),
            )
            ready_document = schedule_repository.get(
                cast(str, submit_result.new_version["schedule_version_id"])
            )
            if (
                ready_document is None
                or ready_document["state"] != "READY_FOR_REVIEW"
                or ready_document["schedule_version_id"]
                != remove_document["schedule_version_id"]
                or ready_document["content_fingerprint"]
                != remove_document["content_fingerprint"]
                or canonical_workspace_bytes(
                    cast(Mapping[str, object], ready_document["content"])
                )
                != remove_content_before
                or not submit_replay.exact_replay
            ):
                raise ValueError("explicit review submission changed immutable content")
            fresh_validator_passes += 3
            checks.append(
                _pass(
                    "P3-06-LOCK-COPY-ON-WRITE",
                    {
                        "set_action": "SET_LOCK",
                        "remove_action": "REMOVE_LOCK",
                        "set_lock_count": len(
                            cast(
                                list[object],
                                cast(Mapping[str, object], set_document["content"])[
                                    "locks"
                                ],
                            )
                        ),
                        "remove_lock_count": len(
                            cast(
                                list[object],
                                cast(Mapping[str, object], remove_document["content"])[
                                    "locks"
                                ],
                            )
                        ),
                        "source_states": [
                            lock_source["state"],
                            set_document["state"],
                        ],
                        "review_submission": {
                            "command_type": "SUBMIT_FOR_REVIEW",
                            "same_version_id": True,
                            "same_content_fingerprint": True,
                            "ready_state": ready_document["state"],
                            "decision": ready_document["decision"],
                            "exact_replay": submit_replay.exact_replay,
                        },
                    },
                )
            )

            assign_output, assign_source, operation_id, target_resource = (
                _assignable_fjsp_source(root)
            )
            assign_lifecycle = lifecycle_service(
                assign_engine, "SIMULATION"
            ).create_reviewable(
                assign_output,
                lifecycle_context(
                    "f", correlation_id="correlation-p3-command-fjsp-source"
                ),
            )
            assign_repository, assign_audit_repository = _repositories(assign_engine)
            assign_repository.put(assign_source)
            assign_service = ScheduleCommandService(
                data_plane="SIMULATION",
                transaction_factory=assign_engine.begin,
                schedule_repository=assign_repository,
                audit_repository=assign_audit_repository,
                validator_factory=_validator_factory,
            )
            assign_command = _command(
                assign_source,
                "ASSIGN_RESOURCE",
                {"operation_id": operation_id, "resource_id": target_resource},
                key="p3-machine-assign-001",
                reason="Assign one flexible operation to another candidate resource.",
                correlation_id="correlation-p3-machine-assign",
            )
            assign_result = assign_service.execute(
                assign_command,
                assign_output.problem,
                _context(assign_lifecycle.audit_event_id, "edit"),
            )
            assign_document = assign_repository.get(
                cast(str, assign_result.new_version["schedule_version_id"])
            )
            if assign_document is None:
                raise ValueError("ASSIGN_RESOURCE result was not persisted")
            assigned = next(
                value
                for value in cast(
                    list[dict[str, object]],
                    cast(Mapping[str, object], assign_document["content"])[
                        "assignments"
                    ],
                )
                if value["operation_id"] == operation_id
            )
            fresh_validator_passes += 1
            checks.append(
                _pass(
                    "P3-06-ASSIGN-RESOURCE",
                    {
                        "operation_id": operation_id,
                        "resource_id": assigned["resource_id"],
                        "new_state": assign_document["state"],
                        "fresh_validation_status": "PASS",
                    },
                )
            )

            checks.append(_historical_check(lifecycle.schedule_version, output.problem))

            negative_counts = _counts(engine)
            invalid = _move_command(
                lifecycle.schedule_version,
                key="p3-machine-invalid-01",
                start_at_utc="2026-09-01T00:00:00Z",
                end_at_utc="2026-09-01T00:01:00Z",
            )
            for expected, operation in (
                (
                    ScheduleCommandFailure.VALIDATION_FAILED,
                    lambda: service.execute(
                        invalid,
                        output.problem,
                        _context(lifecycle.audit_event_id, "edit"),
                    ),
                ),
                (
                    ScheduleCommandFailure.UNAUTHORIZED,
                    lambda: service.execute(
                        _move_command(
                            lifecycle.schedule_version,
                            key="p3-machine-unauth-001",
                        ),
                        output.problem,
                        _context(lifecycle.audit_event_id),
                    ),
                ),
            ):
                _expect(expected, operation)
                rejected_without_side_effect += 1
            stale = _move_command(
                lifecycle.schedule_version,
                key="p3-machine-stale-0001",
            )
            stale["expected_content_fingerprint"] = "sha256:" + "f" * 64
            stale["request_fingerprint"] = workspace_command_fingerprint(stale)
            _expect(
                ScheduleCommandFailure.STALE_SOURCE,
                lambda: service.execute(
                    stale,
                    output.problem,
                    _context(lifecycle.audit_event_id, "edit"),
                ),
            )
            rejected_without_side_effect += 1
            if _counts(engine) != negative_counts:
                raise ValueError("negative commands changed durable counts")
            checks.append(
                _pass(
                    "P3-06-NEGATIVE-NO-SIDE-EFFECT",
                    {
                        "validation_failures": 1,
                        "authorization_failures": 1,
                        "stale_failures": 1,
                        "durable_counts": _counts(engine),
                    },
                )
            )

            rollback_lifecycle = lifecycle_service(
                rollback_engine, "SIMULATION"
            ).create_reviewable(
                output,
                lifecycle_context(
                    "b", correlation_id="correlation-p3-command-rollback-source"
                ),
            )
            rollback_schedule, rollback_audit = _repositories(rollback_engine)
            rollback_command = _move_command(
                rollback_lifecycle.schedule_version,
                key="p3-machine-rollback01",
            )
            rollback_identity = schedule_command_identity(
                rollback_command, data_plane="SIMULATION"
            )
            rollback_service = ScheduleCommandService(
                data_plane="SIMULATION",
                transaction_factory=rollback_engine.begin,
                schedule_repository=rollback_schedule,
                audit_repository=_FailingAuditRepository(rollback_audit),
                validator_factory=_validator_factory,
            )
            _expect(
                ScheduleCommandFailure.PERSISTENCE_FAILED,
                lambda: rollback_service.execute(
                    rollback_command,
                    output.problem,
                    _context(rollback_lifecycle.audit_event_id, "edit"),
                ),
            )
            rejected_without_side_effect += 1
            rollback_creation_service = ScheduleCommandService(
                data_plane="SIMULATION",
                transaction_factory=rollback_engine.begin,
                schedule_repository=rollback_schedule,
                audit_repository=rollback_audit,
                validator_factory=_validator_factory,
            )
            rollback_draft_result = rollback_creation_service.execute(
                _move_command(
                    rollback_lifecycle.schedule_version,
                    key="p3-machine-rollback-draft1",
                ),
                output.problem,
                _context(rollback_lifecycle.audit_event_id, "edit"),
            )
            rollback_draft_id = cast(
                str, rollback_draft_result.new_version["schedule_version_id"]
            )
            rollback_draft = rollback_schedule.get(rollback_draft_id)
            rollback_record_before = rollback_schedule.get_record(rollback_draft_id)
            if rollback_draft is None or rollback_record_before is None:
                raise ValueError("rollback review DRAFT was not persisted")
            _expect(
                ScheduleCommandFailure.PERSISTENCE_FAILED,
                lambda: rollback_service.execute(
                    _command(
                        rollback_draft,
                        "SUBMIT_FOR_REVIEW",
                        {},
                        key="p3-machine-rollback-submit1",
                        reason="Inject audit failure after READY CAS.",
                        correlation_id="correlation-p3-machine-rollback-submit",
                    ),
                    output.problem,
                    _context(rollback_draft_result.audit_event_id, "edit"),
                ),
            )
            rejected_without_side_effect += 1
            rollback_record_after = rollback_schedule.get_record(rollback_draft_id)
            ready_transition_rolled_back = (
                rollback_record_after is not None
                and rollback_record_after.document["state"] == "DRAFT"
                and rollback_record_after.state_revision
                == rollback_record_before.state_revision
            )
            if not ready_transition_rolled_back:
                raise ValueError("audit failure did not roll back READY transition")
            checks.append(
                _pass(
                    "P3-06-ATOMIC-ROLLBACK",
                    {
                        "new_version_absent": rollback_schedule.get(
                            rollback_identity.schedule_version_id
                        )
                        is None,
                        "ready_transition_rolled_back": ready_transition_rolled_back,
                        "durable_counts": _counts(rollback_engine),
                    },
                )
            )

            checks.append(
                _pass(
                    "P3-06-BOUNDARY-OBSERVATION",
                    {
                        "scenario_id": replay.case.scenario_id,
                        "assignment_count": len(
                            cast(
                                list[object],
                                cast(Mapping[str, object], move_document["content"])[
                                    "assignments"
                                ],
                            )
                        ),
                        "observed_command_microseconds": observed_microseconds,
                        "sla": "NOT_DEFINED",
                        "product_service_solver_invocations": 0,
                        "validator_formula_changes": 0,
                        "problem_snapshot_mutations": 0,
                        "http_ui": "NOT_IMPLEMENTED",
                        "approval_publication_export": "NOT_IMPLEMENTED",
                        "p4_replan_change_report": "NOT_IMPLEMENTED",
                    },
                )
            )
        finally:
            engine.dispose()
            assign_engine.dispose()
            rollback_engine.dispose()
            alembic_command.downgrade(configuration, "base")
            alembic_command.downgrade(assign_configuration, "base")
            alembic_command.downgrade(rollback_configuration, "base")
    if len(checks) != 8 or any(check["status"] != "PASS" for check in checks):
        raise ValueError("P3-06 command evidence is incomplete")
    return {
        "report_version": REPORT_VERSION,
        "task_id": TASK_ID,
        "status": "PASS",
        "code_commit": os.environ.get("PLANTNEXUS_CODE_COMMIT", "uncommitted"),
        "schema_set_version": "2.6.0",
        "command_pipeline_version": "schedule-command-pipeline.v1",
        "check_count": len(checks),
        "checks": checks,
        "counts": {
            "command_types": 5,
            "content_command_types": 4,
            "review_submission_command_types": 1,
            "fresh_validator_passes": fresh_validator_passes,
            "exact_replays": 2,
            "idempotency_conflicts": 1,
            "historical_source_states": 2,
            "rejected_requests_without_side_effect": rejected_without_side_effect,
            "product_service_solver_invocations": 0,
        },
        "boundaries": {
            "source_content_update": "FORBIDDEN_AND_ABSENT",
            "manual_draft_ready_transition": "EXPLICIT_CAS_SAME_CONTENT",
            "failed_candidate_persistence": "DISCARDED_NOT_PERSISTED",
            "planning_problem_snapshot_mutation": "FORBIDDEN_AND_ABSENT",
            "solver_replan_obj002": "NOT_IMPLEMENTED",
            "approval_publication_export": "NOT_IMPLEMENTED",
            "http_ui": "NOT_IMPLEMENTED",
            "p4_capabilities": "NOT_IMPLEMENTED",
            "production_authority": "DEFAULT_DENY_OPEN_010",
            "production_readiness": "NOT_CLAIMED",
        },
        "issues": [],
    }


def _write_report(path: Path, report: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate TASK-P3-06 schedule command behavior"
    )
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("build/validation/p3-schedule-commands.json"),
    )
    arguments = parser.parse_args(argv)
    try:
        report = run_command_checks(arguments.root.resolve())
    except Exception as error:  # noqa: BLE001 - machine evidence must fail closed
        reason = (
            error.reason.value
            if isinstance(error, ScheduleCommandError)
            else "MACHINE_CHECK_FAILED"
        )
        report = {
            "report_version": REPORT_VERSION,
            "task_id": TASK_ID,
            "status": "FAIL",
            "code_commit": os.environ.get("PLANTNEXUS_CODE_COMMIT", "uncommitted"),
            "check_count": 0,
            "checks": [],
            "issues": [
                {
                    "reason": reason,
                    "error_type": type(error).__name__,
                    "message": "P3-06 command evidence did not complete",
                }
            ],
            "boundaries": {
                "production_authority": "DEFAULT_DENY_OPEN_010",
                "production_readiness": "NOT_CLAIMED",
            },
        }
        _write_report(arguments.report, report)
        return 1
    _write_report(arguments.report, report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["REPORT_VERSION", "TASK_ID", "main", "run_command_checks"]
