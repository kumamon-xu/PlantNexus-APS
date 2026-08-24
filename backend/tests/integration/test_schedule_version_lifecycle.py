"""TASK-P3-04 atomic persistence, replay, failure, and concurrency tests."""

from __future__ import annotations

from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
from threading import Barrier
from typing import cast

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.application.schedule_version_lifecycle_check import (
    lifecycle_context,
    load_fixed_validated_output,
    main as lifecycle_check_main,
)
from app.application.schedule_versions import (
    ScheduleVersionLifecycleResult,
    ValidatedSolutionToScheduleVersionService,
)
from app.domain.schedule_version import (
    ScheduleVersionLifecycleError,
    ScheduleVersionLifecycleFailure,
    ValidatedPlanningOutput,
    build_reviewable_schedule_documents,
)
from app.infrastructure.audit_repository import SqlAlchemyAuditRepository
from app.infrastructure.schedule_version_repository import (
    SqlAlchemyScheduleVersionRepository,
)
from app.infrastructure.workspace_persistence import WorkspaceDataPlane


ROOT = Path(__file__).resolve().parents[3]


def _alembic_config(database_url: str) -> Config:
    configuration = Config(str(ROOT / "alembic.ini"))
    configuration.set_main_option(
        "script_location", str(ROOT / "backend" / "migrations")
    )
    configuration.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return configuration


@pytest.fixture(scope="module")
def validated_output() -> ValidatedPlanningOutput:
    return load_fixed_validated_output(ROOT)[0]


@pytest.fixture
def workspace_engine(tmp_path: Path) -> Iterator[Engine]:
    database_url = f"sqlite:///{(tmp_path / 'p3-04.db').as_posix()}"
    configuration = _alembic_config(database_url)
    command.upgrade(configuration, "head")
    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    try:
        yield engine
    finally:
        engine.dispose()
        command.downgrade(configuration, "base")


def _counts(engine: Engine) -> tuple[int, int]:
    with engine.connect() as connection:
        return (
            cast(
                int, connection.scalar(text("SELECT COUNT(*) FROM schedule_versions"))
            ),
            cast(int, connection.scalar(text("SELECT COUNT(*) FROM audit_events"))),
        )


def _service(
    engine: Engine, data_plane: WorkspaceDataPlane
) -> ValidatedSolutionToScheduleVersionService:
    return ValidatedSolutionToScheduleVersionService(
        data_plane=data_plane.value,
        transaction_factory=engine.begin,
        schedule_repository=SqlAlchemyScheduleVersionRepository(
            engine, data_plane=data_plane
        ),
        audit_repository=SqlAlchemyAuditRepository(engine, data_plane=data_plane),
    )


def test_service_commits_draft_ready_and_audit_atomically_then_exactly_replays(
    workspace_engine: Engine,
    validated_output: ValidatedPlanningOutput,
) -> None:
    service = _service(workspace_engine, WorkspaceDataPlane.SIMULATION)
    context = lifecycle_context()
    first = service.create_reviewable(validated_output, context)

    assert first.schedule_version["state"] == "READY_FOR_REVIEW"
    assert first.state_revision == 1
    assert not first.schedule_replayed
    assert not first.transition_replayed
    assert not first.audit_replayed
    assert _counts(workspace_engine) == (1, 1)
    stored = SqlAlchemyScheduleVersionRepository(
        workspace_engine, data_plane=WorkspaceDataPlane.SIMULATION
    ).get_record(first.schedule_version_id)
    assert stored is not None
    assert stored.document == first.schedule_version
    assert stored.state_revision == 1
    audits = SqlAlchemyAuditRepository(
        workspace_engine, data_plane=WorkspaceDataPlane.SIMULATION
    ).list_for_aggregate(
        aggregate_type="SCHEDULE_VERSION", aggregate_id=first.schedule_version_id
    )
    assert audits == (first.audit_event,)

    replay = service.create_reviewable(validated_output, context)
    assert replay.exact_replay
    assert replay.schedule_version == first.schedule_version
    assert replay.audit_event == first.audit_event
    assert _counts(workspace_engine) == (1, 1)

    with pytest.raises(ScheduleVersionLifecycleError) as conflict:
        service.create_reviewable(
            validated_output,
            replace(context, reason="Different request reusing the same key."),
        )
    assert conflict.value.reason is ScheduleVersionLifecycleFailure.IDEMPOTENCY_CONFLICT
    assert _counts(workspace_engine) == (1, 1)


def test_validation_lineage_state_and_plane_fail_before_persistence(
    workspace_engine: Engine,
    validated_output: ValidatedPlanningOutput,
) -> None:
    service = _service(workspace_engine, WorkspaceDataPlane.SIMULATION)
    context = lifecycle_context("d")

    with pytest.raises(ScheduleVersionLifecycleError) as state_error:
        service.create_reviewable(
            validated_output, replace(context, planning_run_state="VERIFYING")
        )
    assert (
        state_error.value.reason
        is ScheduleVersionLifecycleFailure.PLANNING_RUN_NOT_COMPLETED
    )

    failed_validation = cast(
        dict[str, object], deepcopy(validated_output.validation_report)
    )
    failed_validation.update(
        {"status": "FAIL", "hard_violation_count": 1, "violations": []}
    )
    with pytest.raises(ScheduleVersionLifecycleError) as validation_error:
        service.create_reviewable(
            replace(validated_output, validation_report=failed_validation), context
        )
    assert (
        validation_error.value.reason
        is ScheduleVersionLifecycleFailure.VALIDATION_FAILED
    )

    changed_kpi = cast(dict[str, object], deepcopy(validated_output.kpi))
    changed_kpi["kpi_id"] = f"kpi-{'f' * 64}"
    with pytest.raises(ScheduleVersionLifecycleError) as lineage_error:
        service.create_reviewable(replace(validated_output, kpi=changed_kpi), context)
    assert lineage_error.value.reason is ScheduleVersionLifecycleFailure.MIXED_LINEAGE

    production_service = _service(workspace_engine, WorkspaceDataPlane.PRODUCTION)
    with pytest.raises(ScheduleVersionLifecycleError) as plane_error:
        production_service.create_reviewable(
            validated_output, replace(context, environment="PRODUCTION")
        )
    assert (
        plane_error.value.reason is ScheduleVersionLifecycleFailure.DATA_PLANE_MISMATCH
    )
    assert _counts(workspace_engine) == (0, 0)


def test_audit_conflict_rolls_back_schedule_creation(
    workspace_engine: Engine,
    validated_output: ValidatedPlanningOutput,
) -> None:
    context = lifecycle_context(
        "e",
        reason="Exercise atomic audit rollback.",
        correlation_id="correlation-p3-04-rollback-test",
    )
    documents = build_reviewable_schedule_documents(
        validated_output, context, data_plane="SIMULATION"
    )
    conflicting_audit = deepcopy(documents.audit_event)
    conflicting_audit["reason"] = "Conflicting pre-existing audit event."
    audit_repository = SqlAlchemyAuditRepository(
        workspace_engine, data_plane=WorkspaceDataPlane.SIMULATION
    )
    audit_repository.append(conflicting_audit)

    service = _service(workspace_engine, WorkspaceDataPlane.SIMULATION)
    with pytest.raises(ScheduleVersionLifecycleError) as conflict:
        service.create_reviewable(validated_output, context)
    assert conflict.value.reason is ScheduleVersionLifecycleFailure.IDEMPOTENCY_CONFLICT
    schedule_repository = SqlAlchemyScheduleVersionRepository(
        workspace_engine, data_plane=WorkspaceDataPlane.SIMULATION
    )
    assert schedule_repository.get(documents.schedule_version_id) is None
    assert _counts(workspace_engine) == (0, 1)


def test_concurrent_exact_requests_are_bounded_and_retry_to_exact_replay(
    workspace_engine: Engine,
    validated_output: ValidatedPlanningOutput,
) -> None:
    context = lifecycle_context(
        "f",
        reason="Exercise concurrent exact lifecycle replay.",
        correlation_id="correlation-p3-04-concurrency-test",
    )
    barrier = Barrier(2)

    def invoke() -> ScheduleVersionLifecycleResult:
        service = _service(workspace_engine, WorkspaceDataPlane.SIMULATION)
        barrier.wait()
        return service.create_reviewable(validated_output, context)

    successes: list[ScheduleVersionLifecycleResult] = []
    failures: list[ScheduleVersionLifecycleFailure] = []
    with ThreadPoolExecutor(max_workers=2) as executor:
        for future in [executor.submit(invoke) for _ in range(2)]:
            try:
                successes.append(future.result())
            except ScheduleVersionLifecycleError as error:
                failures.append(error.reason)
    assert successes
    assert set(failures) <= {
        ScheduleVersionLifecycleFailure.PERSISTENCE_FAILED,
        ScheduleVersionLifecycleFailure.STATE_CONFLICT,
        ScheduleVersionLifecycleFailure.IDEMPOTENCY_CONFLICT,
    }
    assert _counts(workspace_engine) == (1, 1)
    retry = _service(workspace_engine, WorkspaceDataPlane.SIMULATION).create_reviewable(
        validated_output, context
    )
    assert retry.exact_replay


def test_lifecycle_machine_report_is_complete(tmp_path: Path) -> None:
    report_path = tmp_path / "p3-04-lifecycle.json"
    assert (
        lifecycle_check_main(["--root", str(ROOT), "--report", str(report_path)]) == 0
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["report_version"] == "p3-schedule-version-lifecycle-report.v1"
    assert report["task_id"] == "TASK-P3-04"
    assert report["status"] == "PASS"
    assert report["check_count"] == 8
    assert report["issues"] == []
    assert report["counts"]["reviewable_schedule_versions"] == 1
    assert report["counts"]["atomic_audit_events"] == 1
    assert report["counts"]["lifecycle_service_solver_invocations"] == 0
    assert report["boundaries"]["production_readiness"] == "NOT_CLAIMED"
