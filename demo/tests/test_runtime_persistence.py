"""DEMO-RUNTIME: durable control state, reset CAS, and path isolation."""

from __future__ import annotations

from pathlib import Path

import pytest

from plantnexus_demo.orchestration import DemoOperationError, ResetOrchestrator
from plantnexus_demo.persistence import (
    ControlStore,
    DemoPersistenceError,
    DemoRuntimePaths,
    RunDatabase,
    fingerprint,
    key_reference,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
FIXED_TIME = "2026-09-02T08:00:00Z"


def test_runtime_paths_reject_escape_and_absolute_paths(tmp_path: Path) -> None:
    paths = DemoRuntimePaths(tmp_path / "runtime")

    with pytest.raises(DemoPersistenceError, match="PATH_ESCAPE"):
        paths.resolve_relative_database("../outside.db")
    with pytest.raises(DemoPersistenceError, match="PATH_ESCAPE"):
        paths.resolve_relative_database(str((tmp_path / "outside.db").resolve()))
    with pytest.raises(DemoPersistenceError, match="INVALID_IDENTIFIER"):
        paths.run_database("../run")


def test_job_registration_is_exact_replay_mutexed_and_recoverable(
    tmp_path: Path,
) -> None:
    control = ControlStore(DemoRuntimePaths(tmp_path / "runtime"))
    request = {"request_version": "test.v1", "value": 1}
    first = control.register_job(
        job_kind="RESET",
        run_id="run-control-001",
        expected_active_run_id=None,
        request_fingerprint=fingerprint(request),
        key_reference=key_reference("demo-runtime-control-key-0001"),
        correlation_id="correlation-demo-runtime-001",
        request_document=request,
        created_at_utc=FIXED_TIME,
    )
    replay = control.register_job(
        job_kind="RESET",
        run_id="run-control-001",
        expected_active_run_id=None,
        request_fingerprint=fingerprint(request),
        key_reference=key_reference("demo-runtime-control-key-0001"),
        correlation_id="correlation-demo-runtime-001",
        request_document=request,
        created_at_utc=FIXED_TIME,
    )

    assert first.replayed is False
    assert replay.replayed is True
    assert replay.job == first.job
    with pytest.raises(DemoPersistenceError, match="IDEMPOTENCY_CONFLICT"):
        control.register_job(
            job_kind="RESET",
            run_id="run-control-001",
            expected_active_run_id=None,
            request_fingerprint=fingerprint({"request_version": "test.v1", "value": 2}),
            key_reference=key_reference("demo-runtime-control-key-0001"),
            correlation_id="correlation-demo-runtime-002",
            request_document={"request_version": "test.v1", "value": 2},
        )
    with pytest.raises(DemoPersistenceError, match="ACTIVE_JOB_CONFLICT"):
        control.register_job(
            job_kind="INITIAL_PLAN",
            run_id="run-control-001",
            expected_active_run_id=None,
            request_fingerprint=fingerprint({"request_version": "plan.v1"}),
            key_reference=key_reference("demo-runtime-control-key-0002"),
            correlation_id="correlation-demo-runtime-003",
            request_document={"request_version": "plan.v1"},
        )

    control.start_job(first.job.job_id, worker_id="demo-worker-test")
    control.start_stage(first.job.job_id, sequence=1, stage="MIGRATING")
    assert control.recover_interrupted() == 1
    interrupted = control.get_job(first.job.job_id)
    assert interrupted is not None
    assert interrupted.status == "INTERRUPTED"
    assert interrupted.error_code == "PROCESS_INTERRUPTED"
    assert control.job_stages(first.job.job_id)[0]["status"] == "INTERRUPTED"


def test_reset_failure_before_switch_preserves_previous_active_run(
    tmp_path: Path,
) -> None:
    paths = DemoRuntimePaths(tmp_path / "runtime")
    control = ControlStore(paths)
    orchestrator = ResetOrchestrator(
        repository_root=REPOSITORY_ROOT,
        paths=paths,
        control=control,
    )
    first = orchestrator.execute(
        run_id="run-reset-good-001",
        profile_name="smoke",
        expected_active_run_id=None,
        created_at_utc=FIXED_TIME,
    )

    with pytest.raises(DemoOperationError, match="RESET_FAILED"):
        orchestrator.execute(
            run_id="run-reset-failed-002",
            profile_name="smoke",
            expected_active_run_id=first.run_id,
            created_at_utc="2026-09-02T08:01:00Z",
            fault_point="BEFORE_SWITCH",
        )

    active = control.active_run()
    failed = control.get_run("run-reset-failed-002")
    assert active is not None and active.run_id == first.run_id
    assert failed is not None and failed.status == "FAILED"
    database = RunDatabase(
        repository_root=REPOSITORY_ROOT,
        database_path=paths.run_database(first.run_id),
    )
    try:
        assert database.self_check()["status"] == "PASS"
        manifest = database.get_manifest()
        assert manifest is not None
        assert manifest["problem_counts"] == {
            "orders": 24,
            "active_operations": 102,
            "running_operations": 3,
            "not_started_operations": 99,
            "completed_anchors": 3,
            "resources": 12,
            "resource_options": 209,
            "hard_locks": 1,
            "soft_locks": 2,
            "unavailable_intervals": 159,
        }
    finally:
        database.close()
