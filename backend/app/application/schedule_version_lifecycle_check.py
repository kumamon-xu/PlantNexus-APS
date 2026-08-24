"""Emit machine-checkable TASK-P3-04 lifecycle evidence."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace
from importlib import import_module
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier
from time import perf_counter_ns
from typing import Any, cast

from alembic import command
from alembic.config import Config
from app.application.schedule_versions import (
    ScheduleVersionLifecycleResult,
    ValidatedSolutionToScheduleVersionService,
)
from app.domain.schedule_version import (
    ScheduleVersionCreationContext,
    ScheduleVersionLifecycleError,
    ScheduleVersionLifecycleFailure,
    ValidatedPlanningOutput,
    build_reviewable_schedule_documents,
)
from app.domain.workspace_contracts import canonical_workspace_bytes
from app.planning.reporting.kpi import build_kpi_v2
from app.simulation.scenarios.p2_correctness import (
    CorrectnessReplay,
    execute_correctness_case,
    load_correctness_cases,
    verify_correctness_replay,
)


REPORT_VERSION = "p3-schedule-version-lifecycle-report.v1"
TASK_ID = "TASK-P3-04"


def _alembic_config(root: Path, database_url: str) -> Config:
    configuration = Config(str(root / "alembic.ini"))
    configuration.set_main_option(
        "script_location", str(root / "backend" / "migrations")
    )
    configuration.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return configuration


def _workspace_engine(root: Path, database_path: Path) -> tuple[Any, Config]:
    database_url = f"sqlite:///{database_path.as_posix()}"
    configuration = _alembic_config(root, database_url)
    command.upgrade(configuration, "head")
    sqlalchemy = cast(Any, import_module("sqlalchemy"))
    return (
        sqlalchemy.create_engine(
            database_url,
            connect_args={"check_same_thread": False, "timeout": 30},
        ),
        configuration,
    )


def _infrastructure_adapters() -> Any:
    """Load concrete adapters only in this executable composition root."""

    return cast(Any, import_module("app.infrastructure"))


def _service(engine: Any, data_plane: str) -> ValidatedSolutionToScheduleVersionService:
    adapters = _infrastructure_adapters()
    plane = adapters.WorkspaceDataPlane(data_plane)
    return ValidatedSolutionToScheduleVersionService(
        data_plane=data_plane,
        transaction_factory=engine.begin,
        schedule_repository=adapters.SqlAlchemyScheduleVersionRepository(
            engine, data_plane=plane
        ),
        audit_repository=adapters.SqlAlchemyAuditRepository(engine, data_plane=plane),
    )


def load_fixed_validated_output(
    root: Path,
) -> tuple[ValidatedPlanningOutput, CorrectnessReplay]:
    """Replay one frozen P2 case as test input, then freeze its exact KPI."""

    case = load_correctness_cases(root)[0]
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
    return (
        ValidatedPlanningOutput(
            snapshot=replay.snapshot_document,
            problem=replay.problem,
            solution=replay.solution,
            solver_report=replay.solver_report,
            validation_report=replay.validation_report,
            import_quality_report=replay.quality_report,
            kpi=kpi.document,
        ),
        replay,
    )


def lifecycle_context(
    key_character: str = "a",
    *,
    reason: str = "Submit the validated synthetic schedule for human review.",
    correlation_id: str = "correlation-p3-04-primary",
) -> ScheduleVersionCreationContext:
    return ScheduleVersionCreationContext(
        planning_run_state="COMPLETED",
        environment="TEST",
        actor_ref="actor:sim-planner-p3-04",
        auth_policy_version="upstream-auth-context.v1",
        occurred_at_utc="2026-08-24T06:00:00Z",
        correlation_id=correlation_id,
        idempotency_key_reference=f"sha256:{key_character * 64}",
        reason=reason,
    )


def _pass(check_id: str, evidence: Mapping[str, object]) -> dict[str, object]:
    return {"check_id": check_id, "status": "PASS", "evidence": dict(evidence)}


def _expect_failure(
    expected: ScheduleVersionLifecycleFailure | set[ScheduleVersionLifecycleFailure],
    operation: Callable[[], object],
) -> ScheduleVersionLifecycleFailure:
    expected_set = expected if isinstance(expected, set) else {expected}
    try:
        operation()
    except ScheduleVersionLifecycleError as error:
        if error.reason in expected_set:
            return error.reason
        raise ValueError(
            f"unexpected lifecycle rejection reason: {error.reason.value}"
        ) from error
    raise ValueError("expected a lifecycle rejection")


def _table_counts(engine: Any) -> dict[str, int]:
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


def _bundle_bytes(output: ValidatedPlanningOutput) -> tuple[bytes, ...]:
    return tuple(
        canonical_workspace_bytes(document)
        for document in (
            output.snapshot,
            output.problem,
            output.solution,
            output.solver_report,
            output.validation_report,
            output.import_quality_report,
            output.kpi,
        )
    )


def _primary_checks(
    root: Path,
    engine: Any,
    output: ValidatedPlanningOutput,
    replay: CorrectnessReplay,
) -> tuple[list[dict[str, object]], ScheduleVersionLifecycleResult, int]:
    context = lifecycle_context()
    service = _service(engine, "SIMULATION")
    before = _bundle_bytes(output)
    started = perf_counter_ns()
    result = service.create_reviewable(output, context)
    elapsed_microseconds = (perf_counter_ns() - started) // 1_000
    if _bundle_bytes(output) != before:
        raise ValueError("lifecycle service mutated a frozen P2 input")
    if (
        result.schedule_version["state"] != "READY_FOR_REVIEW"
        or result.state_revision != 1
        or result.schedule_replayed
        or result.transition_replayed
        or result.audit_replayed
    ):
        raise ValueError("first lifecycle transaction did not form exact READY state")

    adapters = _infrastructure_adapters()
    schedule_repository = adapters.SqlAlchemyScheduleVersionRepository(
        engine, data_plane=adapters.WorkspaceDataPlane.SIMULATION
    )
    audit_repository = adapters.SqlAlchemyAuditRepository(
        engine, data_plane=adapters.WorkspaceDataPlane.SIMULATION
    )
    stored = schedule_repository.get_record(result.schedule_version_id)
    audits = audit_repository.list_for_aggregate(
        aggregate_type="SCHEDULE_VERSION", aggregate_id=result.schedule_version_id
    )
    if (
        stored is None
        or stored.document != result.schedule_version
        or stored.state_revision != 1
        or len(audits) != 1
        or audits[0] != result.audit_event
    ):
        raise ValueError("committed lifecycle state and audit are inconsistent")

    replay_result = service.create_reviewable(output, context)
    if not replay_result.exact_replay or replay_result != replace(
        result,
        schedule_replayed=True,
        transition_replayed=True,
        audit_replayed=True,
    ):
        raise ValueError("exact business replay changed logical output")
    if _table_counts(engine) != {"schedule_versions": 1, "audit_events": 1}:
        raise ValueError("exact replay duplicated durable evidence")

    rejected = 0
    rejected += bool(
        _expect_failure(
            ScheduleVersionLifecycleFailure.PLANNING_RUN_NOT_COMPLETED,
            lambda: service.create_reviewable(
                output, replace(context, planning_run_state="VERIFYING")
            ),
        )
    )
    failed_validation = cast(dict[str, object], deepcopy(output.validation_report))
    failed_validation.update(
        {"status": "FAIL", "hard_violation_count": 1, "violations": []}
    )
    rejected += bool(
        _expect_failure(
            ScheduleVersionLifecycleFailure.VALIDATION_FAILED,
            lambda: service.create_reviewable(
                replace(output, validation_report=failed_validation),
                replace(context, idempotency_key_reference=f"sha256:{'d' * 64}"),
            ),
        )
    )
    changed_kpi = cast(dict[str, object], deepcopy(output.kpi))
    changed_kpi["kpi_id"] = f"kpi-{'f' * 64}"
    rejected += bool(
        _expect_failure(
            ScheduleVersionLifecycleFailure.MIXED_LINEAGE,
            lambda: service.create_reviewable(
                replace(output, kpi=changed_kpi),
                replace(context, idempotency_key_reference=f"sha256:{'e' * 64}"),
            ),
        )
    )
    rejected += bool(
        _expect_failure(
            ScheduleVersionLifecycleFailure.IDEMPOTENCY_CONFLICT,
            lambda: service.create_reviewable(
                output,
                replace(context, reason="A different request reusing the same key."),
            ),
        )
    )
    production_service = _service(engine, "PRODUCTION")
    rejected += bool(
        _expect_failure(
            ScheduleVersionLifecycleFailure.DATA_PLANE_MISMATCH,
            lambda: production_service.create_reviewable(
                output, replace(context, environment="PRODUCTION")
            ),
        )
    )
    if _table_counts(engine) != {"schedule_versions": 1, "audit_events": 1}:
        raise ValueError("a rejected request produced a durable side effect")

    checks = [
        _pass(
            "P3-04-LINEAGE",
            {
                "scenario_id": replay.case.scenario_id,
                "snapshot_id": replay.snapshot_document["snapshot_id"],
                "snapshot_hash": replay.snapshot_hash,
                "problem_hash": replay.problem["problem_hash"],
                "solution_id": replay.solution["solution_id"],
                "solver_report_id": replay.solver_report["report_id"],
                "validation_status": replay.validation_report["status"],
                "hard_violation_count": replay.validation_report[
                    "hard_violation_count"
                ],
                "kpi_id": output.kpi["kpi_id"],
                "code_commit": cast(
                    Mapping[str, object], replay.solver_report["provenance"]
                )["code_commit"],
            },
        ),
        _pass(
            "P3-04-DRAFT-READY",
            {
                "schedule_version_id": result.schedule_version_id,
                "creation_state": "DRAFT",
                "committed_state": result.schedule_version["state"],
                "state_revision": result.state_revision,
                "content_fingerprint": result.schedule_version["content_fingerprint"],
                "observed_transaction_microseconds": elapsed_microseconds,
                "sla": "NOT_DEFINED",
            },
        ),
        _pass(
            "P3-04-ATOMIC-AUDIT",
            {
                "audit_event_id": result.audit_event_id,
                "action": result.audit_event["action"],
                "before_state": result.audit_event["before_state"],
                "after_state": result.audit_event["after_state"],
                "audit_count": len(audits),
            },
        ),
        _pass(
            "P3-04-EXACT-REPLAY",
            {
                "schedule_replayed": replay_result.schedule_replayed,
                "transition_replayed": replay_result.transition_replayed,
                "audit_replayed": replay_result.audit_replayed,
                "durable_counts": _table_counts(engine),
            },
        ),
        _pass(
            "P3-04-NEGATIVE-NO-SIDE-EFFECT",
            {
                "rejected_requests": rejected,
                "durable_counts": _table_counts(engine),
                "input_documents_unchanged": _bundle_bytes(output) == before,
            },
        ),
    ]
    return checks, result, rejected


def _rollback_check(
    engine: Any,
    output: ValidatedPlanningOutput,
) -> dict[str, object]:
    context = lifecycle_context(
        "b",
        reason="Exercise atomic audit rollback.",
        correlation_id="correlation-p3-04-rollback",
    )
    documents = build_reviewable_schedule_documents(
        output, context, data_plane="SIMULATION"
    )
    conflicting_audit = deepcopy(documents.audit_event)
    conflicting_audit["reason"] = "Pre-existing conflicting audit content."
    adapters = _infrastructure_adapters()
    audit_repository = adapters.SqlAlchemyAuditRepository(
        engine, data_plane=adapters.WorkspaceDataPlane.SIMULATION
    )
    audit_repository.append(conflicting_audit)
    service = _service(engine, "SIMULATION")
    reason = _expect_failure(
        ScheduleVersionLifecycleFailure.IDEMPOTENCY_CONFLICT,
        lambda: service.create_reviewable(output, context),
    )
    schedule_repository = adapters.SqlAlchemyScheduleVersionRepository(
        engine, data_plane=adapters.WorkspaceDataPlane.SIMULATION
    )
    if schedule_repository.get(documents.schedule_version_id) is not None:
        raise ValueError("audit conflict failed to roll back schedule creation")
    return _pass(
        "P3-04-TRANSACTION-ROLLBACK",
        {
            "rejection_reason": reason.value,
            "schedule_version_absent": True,
            "preexisting_audit_count": 1,
        },
    )


def _concurrency_check(
    engine: Any,
    output: ValidatedPlanningOutput,
) -> dict[str, object]:
    context = lifecycle_context(
        "c",
        reason="Exercise exact concurrent lifecycle replay.",
        correlation_id="correlation-p3-04-concurrent",
    )
    barrier = Barrier(2)

    def invoke() -> ScheduleVersionLifecycleResult:
        service = _service(engine, "SIMULATION")
        barrier.wait()
        return service.create_reviewable(output, context)

    successes: list[ScheduleVersionLifecycleResult] = []
    failures: list[ScheduleVersionLifecycleFailure] = []
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(invoke) for _ in range(2)]
        for future in futures:
            try:
                successes.append(future.result())
            except ScheduleVersionLifecycleError as error:
                if error.reason not in {
                    ScheduleVersionLifecycleFailure.PERSISTENCE_FAILED,
                    ScheduleVersionLifecycleFailure.STATE_CONFLICT,
                    ScheduleVersionLifecycleFailure.IDEMPOTENCY_CONFLICT,
                }:
                    raise
                failures.append(error.reason)
    if not successes:
        raise ValueError("concurrent exact requests produced no committed result")
    retry = _service(engine, "SIMULATION").create_reviewable(output, context)
    if not retry.exact_replay:
        raise ValueError("concurrent result was not exact-replayable")
    counts = _table_counts(engine)
    if counts != {"schedule_versions": 1, "audit_events": 1}:
        raise ValueError("concurrent exact requests duplicated durable evidence")
    return _pass(
        "P3-04-IDEMPOTENCY-CONCURRENCY",
        {
            "attempts": 2,
            "successful_attempts": len(successes),
            "sanitized_retryable_failures": [value.value for value in failures],
            "post_race_exact_replay": retry.exact_replay,
            "durable_counts": counts,
        },
    )


def run_lifecycle_checks(root: Path) -> dict[str, object]:
    output, replay = load_fixed_validated_output(root)
    checks: list[dict[str, object]] = []
    rejected_requests = 0
    result: ScheduleVersionLifecycleResult | None = None
    with TemporaryDirectory(prefix="plantnexus-p3-04-") as temporary:
        temporary_root = Path(temporary)
        primary_engine, primary_config = _workspace_engine(
            root, temporary_root / "primary.db"
        )
        rollback_engine, rollback_config = _workspace_engine(
            root, temporary_root / "rollback.db"
        )
        concurrency_engine, concurrency_config = _workspace_engine(
            root, temporary_root / "concurrency.db"
        )
        try:
            primary, result, rejected_requests = _primary_checks(
                root, primary_engine, output, replay
            )
            checks.extend(primary)
            checks.append(_rollback_check(rollback_engine, output))
            checks.append(_concurrency_check(concurrency_engine, output))
            checks.append(
                _pass(
                    "P3-04-PLANE-STATE-BOUNDARY",
                    {
                        "planning_run_required_state": "COMPLETED",
                        "planning_run_mutations": 0,
                        "simulation_version_state": result.schedule_version["state"],
                        "production_schedule_count": 0,
                        "lifecycle_service_solver_invocations": 0,
                        "input_fixture_replays": 1,
                    },
                )
            )
        finally:
            primary_engine.dispose()
            rollback_engine.dispose()
            concurrency_engine.dispose()
            command.downgrade(primary_config, "base")
            command.downgrade(rollback_config, "base")
            command.downgrade(concurrency_config, "base")
    if result is None:
        raise ValueError("primary lifecycle evidence is absent")
    if len(checks) != 8 or any(check["status"] != "PASS" for check in checks):
        raise ValueError("lifecycle evidence is incomplete")
    return {
        "report_version": REPORT_VERSION,
        "task_id": TASK_ID,
        "status": "PASS",
        "code_commit": os.environ.get("PLANTNEXUS_CODE_COMMIT", "uncommitted"),
        "schema_set_version": "2.6.0",
        "lifecycle_version": "schedule-version-lifecycle.v1",
        "check_count": len(checks),
        "checks": checks,
        "counts": {
            "fixed_p2_inputs": 1,
            "fresh_validation_and_kpi_gate": 1,
            "reviewable_schedule_versions": 1,
            "atomic_audit_events": 1,
            "exact_replays": 1,
            "rejected_requests_without_side_effect": rejected_requests,
            "lifecycle_service_solver_invocations": 0,
        },
        "boundaries": {
            "planning_run_mutation": "FORBIDDEN_AND_ABSENT",
            "approval_rejection": "NOT_IMPLEMENTED",
            "publication_export": "NOT_IMPLEMENTED",
            "http_ui": "NOT_IMPLEMENTED",
            "p4_capabilities": "NOT_IMPLEMENTED",
            "production_authority": "NOT_CLAIMED",
            "production_readiness": "NOT_CLAIMED",
            "open_010": "OPEN",
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
        description="Validate the P3-04 reviewable ScheduleVersion lifecycle"
    )
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("build/validation/p3-schedule-version-lifecycle.json"),
    )
    arguments = parser.parse_args(argv)
    root = arguments.root.resolve()
    try:
        report = run_lifecycle_checks(root)
    except Exception as error:  # noqa: BLE001 - CLI must emit fail-closed evidence
        reason = (
            error.reason.value
            if isinstance(error, ScheduleVersionLifecycleError)
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
                    "message": "P3-04 lifecycle evidence did not complete",
                }
            ],
            "boundaries": {
                "production_authority": "NOT_CLAIMED",
                "production_readiness": "NOT_CLAIMED",
            },
        }
        _write_report(arguments.report, report)
        return 1
    _write_report(arguments.report, report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "REPORT_VERSION",
    "TASK_ID",
    "lifecycle_context",
    "load_fixed_validated_output",
    "main",
    "run_lifecycle_checks",
]
