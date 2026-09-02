"""DEMO-PLAN/BASELINE: real Solver, Validator, version, and publication chain."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.infrastructure.publication_repository import SqlAlchemyPublicationRepository
from app.infrastructure.schedule_version_repository import (
    SqlAlchemyScheduleVersionRepository,
)
from app.infrastructure.workspace_persistence import WorkspaceDataPlane

from plantnexus_demo.orchestration import (
    BaselineActivationService,
    DemoOperationError,
    InitialPlanningOrchestrator,
    ResetOrchestrator,
)
from plantnexus_demo.persistence import (
    ControlStore,
    DemoRuntimePaths,
    RunDatabase,
    fingerprint,
    key_reference,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
FIXED_TIME = "2026-09-02T09:00:00Z"


def _initialized(tmp_path: Path, suffix: str) -> tuple[DemoRuntimePaths, ControlStore, str]:
    paths = DemoRuntimePaths(tmp_path / f"runtime-{suffix}")
    control = ControlStore(paths)
    run_id = f"run-plan-{suffix}"
    ResetOrchestrator(
        repository_root=REPOSITORY_ROOT, paths=paths, control=control
    ).execute(
        run_id=run_id,
        profile_name="smoke",
        expected_active_run_id=None,
        created_at_utc=FIXED_TIME,
    )
    return paths, control, run_id


def _plan(
    paths: DemoRuntimePaths, control: ControlStore, run_id: str, suffix: str
):
    request_fingerprint = fingerprint(
        {"request_version": "cnc-demo-initial-plan-request.v1", "run_id": run_id}
    )
    return InitialPlanningOrchestrator(
        repository_root=REPOSITORY_ROOT,
        paths=paths,
        control=control,
    ).execute(
        run_id=run_id,
        request_fingerprint=request_fingerprint,
        idempotency_key_reference=key_reference(
            f"demo-initial-plan-idempotency-{suffix}-0001"
        ),
        correlation_id=f"correlation-demo-plan-{suffix}",
        occurred_at_utc="2026-09-02T09:05:00Z",
    )


def test_initial_plan_creates_ready_version_and_complete_artifact_set(
    tmp_path: Path,
) -> None:
    paths, control, run_id = _initialized(tmp_path, "ready-001")
    result = _plan(paths, control, run_id, "ready-001")

    assert result.schedule_state == "READY_FOR_REVIEW"
    assert result.state_revision == 1
    assert result.solver_status in {"OPTIMAL", "FEASIBLE"}
    assert result.validation_status == "PASS"
    database = RunDatabase(
        repository_root=REPOSITORY_ROOT,
        database_path=paths.run_database(run_id),
    )
    try:
        schedule = SqlAlchemyScheduleVersionRepository(
            database.engine, data_plane=WorkspaceDataPlane.SIMULATION
        ).get_record(result.schedule_version_id)
        assert schedule is not None
        assert schedule.document["state"] == "READY_FOR_REVIEW"
        assert schedule.document["content_fingerprint"] == result.content_fingerprint
        assert {item["artifact_kind"] for item in database.list_artifacts()} == {
            "IMPORT_QUALITY",
            "SNAPSHOT",
            "PLANNING_PROBLEM",
            "PLANNING_SOLUTION",
            "SOLVER_REPORT",
            "VALIDATION_REPORT",
            "KPI",
        }
    finally:
        database.close()


def test_mutated_validation_blocks_schedule_creation(tmp_path: Path) -> None:
    paths, control, run_id = _initialized(tmp_path, "mutation-001")
    orchestrator = InitialPlanningOrchestrator(
        repository_root=REPOSITORY_ROOT,
        paths=paths,
        control=control,
    )
    with pytest.raises(DemoOperationError, match="SOLUTION_VALIDATION_FAILED"):
        orchestrator.execute(
            run_id=run_id,
            request_fingerprint=fingerprint({"mutation": True}),
            idempotency_key_reference=key_reference(
                "demo-initial-plan-mutation-idempotency-0001"
            ),
            correlation_id="correlation-demo-plan-mutation",
            occurred_at_utc="2026-09-02T09:06:00Z",
            validation_override={
                "validation_report_version": "validation-report.v2",
                "problem_hash": "sha256:" + "0" * 64,
                "status": "FAIL",
                "hard_violation_count": 1,
                "violations": [],
            },
        )
    database = RunDatabase(
        repository_root=REPOSITORY_ROOT,
        database_path=paths.run_database(run_id),
    )
    try:
        with database.engine.connect() as connection:
            count = connection.exec_driver_sql(
                "SELECT COUNT(*) FROM schedule_versions"
            ).scalar_one()
        assert count == 0
    finally:
        database.close()


def test_baseline_activation_publishes_current_and_exactly_replays(
    tmp_path: Path,
) -> None:
    paths, control, run_id = _initialized(tmp_path, "publish-001")
    planned = _plan(paths, control, run_id, "publish-001")
    service = BaselineActivationService(
        repository_root=REPOSITORY_ROOT, paths=paths, control=control
    )
    key_ref = key_reference("demo-baseline-activation-publish-0001")
    activated = service.execute(
        expected_run_id=run_id,
        schedule_version_id=planned.schedule_version_id,
        content_fingerprint=planned.content_fingerprint,
        expected_state_revision=planned.state_revision,
        confirmation="ACTIVATE_SIMULATION_BASELINE",
        idempotency_key_reference=key_ref,
        correlation_id="correlation-demo-baseline-publish",
        occurred_at_utc="2026-09-02T09:10:00Z",
    )
    replay = service.execute(
        expected_run_id=run_id,
        schedule_version_id=planned.schedule_version_id,
        content_fingerprint=planned.content_fingerprint,
        expected_state_revision=planned.state_revision,
        confirmation="ACTIVATE_SIMULATION_BASELINE",
        idempotency_key_reference=key_ref,
        correlation_id="correlation-demo-baseline-publish",
        occurred_at_utc="2026-09-02T09:11:00Z",
    )

    assert activated.state == "PUBLISHED"
    assert activated.state_revision == 3
    assert replay.replayed is True
    assert replay.document | {"replayed": False} == activated.document
    database = RunDatabase(
        repository_root=REPOSITORY_ROOT,
        database_path=paths.run_database(run_id),
    )
    try:
        current = SqlAlchemyPublicationRepository(
            database.engine, data_plane=WorkspaceDataPlane.SIMULATION
        ).get_current(target="SIMULATION_INTERNAL")
        assert current is not None
        assert current.schedule_version_id == planned.schedule_version_id
        assert current.content_fingerprint == planned.content_fingerprint
    finally:
        database.close()


def test_activation_resumes_same_identity_after_approval_only_failure(
    tmp_path: Path,
) -> None:
    paths, control, run_id = _initialized(tmp_path, "resume-001")
    planned = _plan(paths, control, run_id, "resume-001")
    service = BaselineActivationService(
        repository_root=REPOSITORY_ROOT, paths=paths, control=control
    )
    key_ref = key_reference("demo-baseline-activation-resume-0001")
    arguments = {
        "expected_run_id": run_id,
        "schedule_version_id": planned.schedule_version_id,
        "content_fingerprint": planned.content_fingerprint,
        "expected_state_revision": planned.state_revision,
        "confirmation": "ACTIVATE_SIMULATION_BASELINE",
        "idempotency_key_reference": key_ref,
        "correlation_id": "correlation-demo-baseline-resume",
        "occurred_at_utc": "2026-09-02T09:15:00Z",
    }
    with pytest.raises(DemoOperationError, match="PUBLISH_FAILED"):
        service.execute(**arguments, fail_after_approval=True)

    database = RunDatabase(
        repository_root=REPOSITORY_ROOT,
        database_path=paths.run_database(run_id),
    )
    try:
        approved = SqlAlchemyScheduleVersionRepository(
            database.engine, data_plane=WorkspaceDataPlane.SIMULATION
        ).get(planned.schedule_version_id)
        assert approved is not None and approved["state"] == "APPROVED"
    finally:
        database.close()
    resumed = service.execute(**arguments)
    assert resumed.state == "PUBLISHED"
    assert resumed.replayed is True
