"""Run the D16 API, SQLite, recovery, concurrency, and security audit."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from hashlib import sha256
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
from threading import Barrier
from time import perf_counter
from typing import Any
from zoneinfo import ZoneInfo


DEMO_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = DEMO_ROOT.parent
sys.path.insert(0, str(REPOSITORY_ROOT / "backend"))
sys.path.insert(0, str(DEMO_ROOT / "backend"))

from fastapi.testclient import TestClient  # noqa: E402
from pydantic import SecretStr  # noqa: E402

from app.api.app import create_app  # noqa: E402
from app.infrastructure.config import (  # noqa: E402
    DataPlane,
    RuntimeEnvironment,
    Settings,
)
from plantnexus_demo.composition import create_demo_app  # noqa: E402
from plantnexus_demo.jobs import DemoJobRunner, DemoJobService  # noqa: E402
from plantnexus_demo.orchestration import (  # noqa: E402
    DemoOperationError,
    ResetOrchestrator,
)
from plantnexus_demo.persistence import (  # noqa: E402
    ControlStore,
    DemoPersistenceError,
    DemoRuntimePaths,
    fingerprint,
    key_reference,
    resolve_named_runtime_root,
)  # noqa: E402
from plantnexus_demo.security import (  # noqa: E402
    SimulationLocalAuthorizationProvider,
)


EVIDENCE_VERSION = "cnc-demo-e2e-audit.v1"
TASK_ID = "TASK-DEMO-08"
FIXED_TIME = "2026-09-02T08:00:00Z"


class AuditFailure(RuntimeError):
    """Internal assertion with a stable, non-secret label."""


def _require(condition: bool, label: str) -> None:
    if not condition:
        raise AuditFailure(label)


def _fingerprint(document: dict[str, Any]) -> str:
    payload = json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return f"sha256:{sha256(payload).hexdigest()}"


def _control_count(paths: DemoRuntimePaths, table: str) -> int:
    if table not in {"demo_jobs", "demo_authorization_audit"}:
        raise ValueError("unsupported control table")
    with sqlite3.connect(paths.control_database) as connection:
        row = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
    assert row is not None
    return int(row[0])


def _job_duration(job: Any) -> float:
    started = datetime.fromisoformat(job.created_at_utc.replace("Z", "+00:00"))
    finished = datetime.fromisoformat(job.updated_at_utc.replace("Z", "+00:00"))
    return max(0.0, (finished - started).total_seconds())


def _concurrency_audit(root: Path) -> dict[str, Any]:
    control = ControlStore(DemoRuntimePaths(root / "concurrency"))
    barrier = Barrier(2)

    def register(index: int) -> str:
        request = {"request_version": "concurrent.v1", "value": index}
        barrier.wait()
        try:
            control.register_job(
                job_kind="RESET",
                run_id=f"run-audit-concurrent-{index}",
                expected_active_run_id=None,
                request_fingerprint=fingerprint(request),
                key_reference=key_reference(
                    f"demo-audit-concurrent-idempotency-{index:04d}"
                ),
                correlation_id=f"correlation-demo-audit-concurrent-{index}",
                request_document=request,
                created_at_utc=FIXED_TIME,
            )
        except DemoPersistenceError as error:
            return error.code
        return "ACCEPTED"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = sorted(executor.map(register, (1, 2)))
    _require(outcomes == ["ACCEPTED", "ACTIVE_JOB_CONFLICT"], "concurrency_mutex")
    return {"outcomes": outcomes, "durable_jobs": _control_count(control.paths, "demo_jobs")}


def _restart_audit(root: Path) -> dict[str, Any]:
    paths = DemoRuntimePaths(root / "restart")
    control = ControlStore(paths)
    idempotency_key = "demo-audit-interrupted-reset-0001"
    key_ref = key_reference(idempotency_key)
    run_id = "run-" + sha256(f"RESET:{key_ref}".encode("utf-8")).hexdigest()[:32]
    request = {
        "request_version": "cnc-demo-reset-request.v1",
        "profile_name": "smoke",
        "expected_active_run_id": None,
    }
    registration = control.register_job(
        job_kind="RESET",
        run_id=run_id,
        expected_active_run_id=None,
        request_fingerprint=fingerprint(request),
        key_reference=key_ref,
        correlation_id="correlation-demo-audit-restart",
        request_document=request,
        created_at_utc=FIXED_TIME,
    )
    control.start_job(registration.job.job_id, worker_id="demo-worker-before-restart")
    control.start_stage(registration.job.job_id, sequence=1, stage="MIGRATING")

    runner = DemoJobRunner(
        repository_root=REPOSITORY_ROOT,
        paths=paths,
        control=control,
        auto_resume_queued=False,
    )
    interrupted = control.get_job(registration.job.job_id)
    _require(interrupted is not None, "restart_job_present")
    assert interrupted is not None
    _require(interrupted.status == "INTERRUPTED", "restart_status_interrupted")
    _require(interrupted.error_code == "PROCESS_INTERRUPTED", "restart_code")
    stages = control.job_stages(registration.job.job_id)
    _require(stages[0]["status"] == "INTERRUPTED", "restart_stage_interrupted")

    service = DemoJobService(control=control, runner=runner)
    try:
        replay = service.accept_reset(
            profile_name="smoke",
            idempotency_key=idempotency_key,
            correlation_id="correlation-demo-audit-restart-retry",
        )
        completed = runner.wait(replay.job_id, timeout=45)
    finally:
        runner.shutdown()
    _require(replay.replayed, "restart_exact_replay")
    _require(replay.job_id == registration.job.job_id, "restart_same_job")
    _require(completed.status == "SUCCEEDED", "restart_retry_succeeded")
    _require(completed.attempt == 2, "restart_attempt_incremented")
    return {
        "interrupted_status": interrupted.status,
        "error_code": interrupted.error_code,
        "replayed": replay.replayed,
        "same_job_identity": replay.job_id == registration.job.job_id,
        "retry_status": completed.status,
        "attempt": completed.attempt,
    }


def _reset_failure_audit(root: Path) -> dict[str, Any]:
    paths = DemoRuntimePaths(root / "reset-failure")
    control = ControlStore(paths)
    orchestrator = ResetOrchestrator(
        repository_root=REPOSITORY_ROOT,
        paths=paths,
        control=control,
    )
    first = orchestrator.execute(
        run_id="run-audit-reset-good-001",
        profile_name="smoke",
        expected_active_run_id=None,
        created_at_utc=FIXED_TIME,
    )
    error_code = None
    try:
        orchestrator.execute(
            run_id="run-audit-reset-failed-002",
            profile_name="smoke",
            expected_active_run_id=first.run_id,
            created_at_utc="2026-09-02T08:01:00Z",
            fault_point="BEFORE_SWITCH",
        )
    except DemoOperationError as error:
        error_code = error.code
    active = control.active_run()
    failed = control.get_run("run-audit-reset-failed-002")
    _require(error_code == "RESET_FAILED", "reset_fault_code")
    _require(active is not None and active.run_id == first.run_id, "reset_preserves_active")
    _require(failed is not None and failed.status == "FAILED", "reset_marks_candidate_failed")
    assert failed is not None
    return {
        "error_code": error_code,
        "previous_active_preserved": True,
        "failed_candidate_status": failed.status,
    }


def _path_audit(root: Path) -> dict[str, Any]:
    paths = DemoRuntimePaths(root / "paths")
    rejected: list[str] = []
    for candidate in ("../outside.db", str((root / "outside.db").resolve())):
        try:
            paths.resolve_relative_database(candidate)
        except DemoPersistenceError as error:
            rejected.append(error.code)
    invalid_runtime_ids = ("../outside", "C:/outside", "nested/runtime", "UPPER", "")
    for runtime_id in invalid_runtime_ids:
        try:
            resolve_named_runtime_root(DEMO_ROOT, runtime_id)
        except ValueError:
            rejected.append("INVALID_RUNTIME_ID")
    _require(
        rejected == ["PATH_ESCAPE", "PATH_ESCAPE", *(["INVALID_RUNTIME_ID"] * 5)],
        "path_escape_matrix",
    )
    return {
        "database_paths_rejected": 2,
        "runtime_ids_rejected": len(invalid_runtime_ids),
        "broad_delete_target_exposed": False,
    }


def _production_binding_audit() -> dict[str, Any]:
    sentinel = "production-binding-sentinel-must-not-leak"
    application = create_app(
        Settings(
            runtime_environment=RuntimeEnvironment.PRODUCTION,
            data_plane=DataPlane.PRODUCTION,
            simulation_api_enabled=False,
            code_commit="0" * 40,
            database_url=SecretStr(
                "postgresql+psycopg://plantnexus@localhost:5432/plantnexus"
            ),
        ),
        probes={},
        authorization_provider=SimulationLocalAuthorizationProvider(sentinel),
    )
    with TestClient(application) as client:
        response = client.get(
            "/api/v1/schedule-versions/schedule-version-production",
            headers={"Authorization": f"Bearer {sentinel}"},
        )
    _require(response.status_code == 403, "production_binding_denied")
    _require(sentinel not in response.text, "production_token_sanitized")
    return {
        "status_code": response.status_code,
        "production_binding_granted": False,
        "sentinel_exposed": False,
    }


def _scan_for_token(token: str, runtime_root: Path) -> dict[str, Any]:
    token_bytes = token.encode("utf-8")
    leaked_paths: list[str] = []
    for path in DEMO_ROOT.rglob("*"):
        if not path.is_file():
            continue
        try:
            path.resolve().relative_to(runtime_root.resolve())
        except ValueError:
            pass
        else:
            continue
        if any(
            part in {"node_modules", "dist", ".playwright-cli", "__pycache__"}
            for part in path.parts
        ):
            continue
        if token_bytes in path.read_bytes():
            leaked_paths.append(path.relative_to(DEMO_ROOT).as_posix())
    _require(not leaked_paths, "token_repository_scan")
    _require(token_bytes not in (runtime_root / "control.db").read_bytes(), "token_control_db")
    return {
        "repository_matches": leaked_paths,
        "control_database_contains_token": False,
        "token_file_inside_runtime": (runtime_root / "session.token").is_file(),
    }


def _main_flow(runtime_root: Path) -> tuple[dict[str, Any], str]:
    application = create_demo_app(
        repository_root=REPOSITORY_ROOT,
        runtime_root=runtime_root,
        auto_resume_queued=False,
    )
    runtime = application.state.demo_runtime
    assertions: dict[str, bool] = {}
    response_bodies: list[str] = []
    jobs: dict[str, dict[str, Any]] = {}

    def check(name: str, condition: bool) -> None:
        assertions[name] = condition
        _require(condition, name)

    with TestClient(application) as client:
        unauthenticated = client.get("/api/demo/v1/bootstrap")
        response_bodies.append(unauthenticated.text)
        check("unauthenticated_read_denied", unauthenticated.status_code == 401)

        session = client.post("/api/demo/v1/session")
        response_bodies.append(session.text)
        set_cookie = session.headers.get("set-cookie", "")
        check("session_established", session.status_code == 200)
        check("session_cookie_http_only", "httponly" in set_cookie.lower())
        check("session_cookie_same_site_strict", "samesite=strict" in set_cookie.lower())
        check("session_body_has_no_token", runtime.local_token not in session.text)

        empty = client.get("/api/demo/v1/bootstrap")
        response_bodies.append(empty.text)
        empty_document = empty.json()
        check("starts_from_empty_runtime", empty_document["story_state"] == "EMPTY")
        check("empty_is_simulation_only", empty_document["simulation_only"] is True)
        check("empty_has_no_production_authority", empty_document["production_authority"] is False)

        reset_key = "demo-audit-reset-idempotency-0001"
        reset = client.post(
            "/api/demo/v1/resets",
            headers={"Idempotency-Key": reset_key},
            json={
                "request_version": "cnc-demo-reset-request.v1",
                "profile_name": "smoke",
            },
        )
        response_bodies.append(reset.text)
        check("reset_accepted", reset.status_code == 202)
        reset_job = runtime.runner.wait(reset.json()["job_id"], timeout=45)
        check("reset_succeeded", reset_job.status == "SUCCEEDED")
        run_id = str(reset_job.result["run_id"])
        jobs["reset"] = {
            "job_id": reset_job.job_id,
            "status": reset_job.status,
            "attempt": reset_job.attempt,
            "wall_seconds": _job_duration(reset_job),
        }

        reset_replay = client.post(
            "/api/demo/v1/resets",
            headers={"Idempotency-Key": reset_key},
            json={
                "request_version": "cnc-demo-reset-request.v1",
                "profile_name": "smoke",
            },
        )
        response_bodies.append(reset_replay.text)
        check("reset_exact_replay", reset_replay.json()["replayed"] is True)
        check("reset_replay_same_job", reset_replay.json()["job_id"] == reset_job.job_id)

        job_count = _control_count(runtime.paths, "demo_jobs")
        reset_conflict = client.post(
            "/api/demo/v1/resets",
            headers={"Idempotency-Key": reset_key},
            json={
                "request_version": "cnc-demo-reset-request.v1",
                "profile_name": "showcase",
            },
        )
        response_bodies.append(reset_conflict.text)
        check("idempotency_conflict_rejected", reset_conflict.status_code == 409)
        check("idempotency_conflict_code", reset_conflict.json()["code"] == "IDEMPOTENCY_CONFLICT")
        check("idempotency_conflict_no_write", _control_count(runtime.paths, "demo_jobs") == job_count)

        stale_plan = client.post(
            "/api/demo/v1/initial-plans",
            headers={"Idempotency-Key": "demo-audit-stale-plan-0001"},
            json={
                "request_version": "cnc-demo-initial-plan-request.v1",
                "expected_run_id": "run-stale-demo-audit",
            },
        )
        response_bodies.append(stale_plan.text)
        check("stale_run_rejected", stale_plan.status_code == 409)
        check("stale_run_code", stale_plan.json()["code"] == "STALE_RUN")
        check("stale_run_no_write", _control_count(runtime.paths, "demo_jobs") == job_count)

        plan = client.post(
            "/api/demo/v1/initial-plans",
            headers={"Idempotency-Key": "demo-audit-plan-idempotency-0001"},
            json={
                "request_version": "cnc-demo-initial-plan-request.v1",
                "expected_run_id": run_id,
            },
        )
        response_bodies.append(plan.text)
        check("initial_plan_accepted", plan.status_code == 202)
        plan_job = runtime.runner.wait(plan.json()["job_id"], timeout=45)
        check("initial_plan_succeeded", plan_job.status == "SUCCEEDED")
        check("initial_plan_validator_pass", plan_job.result["validation_status"] == "PASS")
        schedule_version_id = str(plan_job.result["schedule_version_id"])
        jobs["initial_plan"] = {
            "job_id": plan_job.job_id,
            "status": plan_job.status,
            "attempt": plan_job.attempt,
            "wall_seconds": _job_duration(plan_job),
            "solver_status": plan_job.result["solver_status"],
            "validation_status": plan_job.result["validation_status"],
        }

        schedule = client.get(f"/api/demo/v1/versions/{schedule_version_id}?limit=1")
        response_bodies.append(schedule.text)
        schedule_document = schedule.json()
        check("ready_version_read", schedule_document["version"]["state"] == "READY_FOR_REVIEW")
        check("ready_version_not_publishable", schedule_document["boundary"]["publishable"] is False)

        activation = client.post(
            "/api/demo/v1/baseline-activations",
            headers={"Idempotency-Key": "demo-audit-activation-idempotency-0001"},
            json={
                "command_version": "cnc-demo-baseline-activation.v1",
                "expected_run_id": run_id,
                "schedule_version_id": schedule_version_id,
                "content_fingerprint": schedule_document["version"]["content_fingerprint"],
                "expected_state_revision": schedule_document["version"]["revision"],
                "confirmation": "ACTIVATE_SIMULATION_BASELINE",
            },
        )
        response_bodies.append(activation.text)
        check("baseline_activation_succeeded", activation.status_code == 200)
        check("baseline_is_published", activation.json()["state"] == "PUBLISHED")

        manifest = client.get("/api/demo/v1/bootstrap").json()["scenario_manifest"]
        start = datetime.fromisoformat(
            str(manifest["horizon_start_utc"]).replace("Z", "+00:00")
        ).astimezone(ZoneInfo("Asia/Shanghai"))
        due_at_local = (start + timedelta(hours=60)).strftime("%Y-%m-%dT%H:%M:%S")

        stale_base = client.post(
            "/api/demo/v1/urgent-orders",
            headers={"Idempotency-Key": "demo-audit-stale-urgent-0001"},
            json={
                "command_version": "cnc-demo-urgent-order-command.v1",
                "expected_run_id": run_id,
                "expected_base_version_id": "schedule-version-stale-demo-audit",
                "route_template_id": "CNC-ROUTE-5",
                "quantity": 5,
                "due_at_local": due_at_local,
                "priority_class": "URGENT",
                "note": "D16 合成数据 stale 检查",
            },
        )
        response_bodies.append(stale_base.text)
        check("stale_base_rejected", stale_base.status_code == 409)
        check("stale_base_code", stale_base.json()["code"] == "STALE_BASE_VERSION")

        urgent = client.post(
            "/api/demo/v1/urgent-orders",
            headers={"Idempotency-Key": "demo-audit-urgent-idempotency-0001"},
            json={
                "command_version": "cnc-demo-urgent-order-command.v1",
                "expected_run_id": run_id,
                "expected_base_version_id": schedule_version_id,
                "route_template_id": "CNC-ROUTE-5",
                "quantity": 5,
                "due_at_local": due_at_local,
                "priority_class": "URGENT",
                "note": "D16 固定合成数据加急订单",
            },
        )
        response_bodies.append(urgent.text)
        check("urgent_accepted", urgent.status_code == 202)
        urgent_job = runtime.runner.wait(urgent.json()["job_id"], timeout=60)
        check("urgent_succeeded", urgent_job.status == "SUCCEEDED")
        check("urgent_validator_pass", urgent_job.result["validation_status"] == "PASS")
        check("urgent_result_is_draft", urgent_job.result["schedule_state"] == "DRAFT")
        check(
            "published_baseline_unchanged",
            urgent_job.result["current_published_version_id"] == schedule_version_id,
        )
        jobs["urgent_replan"] = {
            "job_id": urgent_job.job_id,
            "status": urgent_job.status,
            "attempt": urgent_job.attempt,
            "wall_seconds": _job_duration(urgent_job),
            "solver_status": urgent_job.result["solver_status"],
            "validation_status": urgent_job.result["validation_status"],
        }

        state = client.get("/api/demo/v1/bootstrap")
        response_bodies.append(state.text)
        state_document = state.json()
        check("comparison_story_ready", state_document["story_state"] == "DRAFT_COMPARISON_READY")
        check(
            "comparison_reference_exact",
            state_document["comparison_reference"]["request_id"]
            == urgent_job.result["request_id"],
        )
        check(
            "current_publication_still_baseline",
            state_document["current_publication"]["schedule_version_id"]
            == schedule_version_id,
        )

        comparison = client.get(
            f"/api/demo/v1/comparisons/{urgent_job.result['request_id']}?limit=120"
        )
        response_bodies.append(comparison.text)
        comparison_document = comparison.json()
        check("comparison_read_succeeded", comparison.status_code == 200)
        check("comparison_before_published", comparison_document["before"]["state"] == "PUBLISHED")
        check("comparison_after_draft", comparison_document["after"]["state"] == "DRAFT")
        check("comparison_added_five", comparison_document["change_counts"]["added"] == 5)
        check(
            "comparison_change_report_pass",
            comparison_document["provenance"]["validation_status"] == "PASS",
        )
        check("comparison_page_bounded", comparison_document["page"]["limit"] == 120)

        wrong_token = client.get(
            "/api/demo/v1/bootstrap",
            headers={"Authorization": "Bearer demo-audit-wrong-secret"},
        )
        response_bodies.append(wrong_token.text)
        check("wrong_token_denied", wrong_token.status_code == 401)
        check("wrong_token_sanitized", "demo-audit-wrong-secret" not in wrong_token.text)

        original_provider = application.state.authorization_provider
        application.state.authorization_provider = SimulationLocalAuthorizationProvider(
            runtime.local_token,
            capabilities=frozenset({"view"}),
        )
        denied_capability = client.post(
            "/api/demo/v1/resets",
            headers={
                "Authorization": f"Bearer {runtime.local_token}",
                "Idempotency-Key": "demo-audit-denied-reset-0001",
            },
            json={
                "request_version": "cnc-demo-reset-request.v1",
                "profile_name": "smoke",
            },
        )
        response_bodies.append(denied_capability.text)
        check("missing_capability_denied", denied_capability.status_code == 403)
        check("capability_denial_sanitized", runtime.local_token not in denied_capability.text)

        application.state.authorization_provider = SimulationLocalAuthorizationProvider(
            runtime.local_token,
            capabilities=frozenset({"view"}),
            schedule_version_scope=frozenset({"schedule-version-in-scope"}),
        )
        denied_scope = client.get(
            f"/api/demo/v1/versions/{schedule_version_id}",
            headers={"Authorization": f"Bearer {runtime.local_token}"},
        )
        response_bodies.append(denied_scope.text)
        check("wrong_scope_denied", denied_scope.status_code == 403)
        check("scope_denial_sanitized", runtime.local_token not in denied_scope.text)
        application.state.authorization_provider = original_provider

        remote_client = TestClient(application, client=("203.0.113.10", 443))
        try:
            remote_session = remote_client.post("/api/demo/v1/session")
        finally:
            remote_client.close()
        response_bodies.append(remote_session.text)
        check("non_loopback_session_denied", remote_session.status_code == 403)
        check("remote_denial_code", remote_session.json()["code"] == "AUTHORIZATION_DENIED")

        check(
            "all_http_bodies_token_safe",
            all(runtime.local_token not in body for body in response_bodies),
        )

    return (
        {
            "assertions": assertions,
            "run_id": run_id,
            "story_state": state_document["story_state"],
            "before_schedule_version_id": schedule_version_id,
            "after_schedule_version_id": urgent_job.result["schedule_version_id"],
            "request_id": urgent_job.result["request_id"],
            "change_report_id": urgent_job.result["change_report_id"],
            "jobs": jobs,
            "comparison": {
                "change_counts": comparison_document["change_counts"],
                "validation_status": comparison_document["provenance"][
                    "validation_status"
                ],
                "page_limit": comparison_document["page"]["limit"],
            },
            "authorization_audit_records": _control_count(
                runtime.paths, "demo_authorization_audit"
            ),
        },
        runtime.local_token,
    )


def build_report() -> dict[str, Any]:
    runtime_parent = DEMO_ROOT / "runtime"
    runtime_parent.mkdir(parents=True, exist_ok=True)
    temporary_root = Path(
        tempfile.mkdtemp(prefix="audit-demo-08-", dir=runtime_parent)
    ).resolve()
    started = perf_counter()
    try:
        main_flow, token = _main_flow(temporary_root / "main")
        report: dict[str, Any] = {
            "evidence_version": EVIDENCE_VERSION,
            "task_id": TASK_ID,
            "status": "PASS",
            "main_flow": main_flow,
            "recovery": _restart_audit(temporary_root),
            "reset_failure": _reset_failure_audit(temporary_root),
            "concurrency": _concurrency_audit(temporary_root),
            "path_security": _path_audit(temporary_root),
            "production_binding": _production_binding_audit(),
            "secret_hygiene": _scan_for_token(token, temporary_root / "main"),
            "audit_wall_seconds": perf_counter() - started,
            "boundaries": {
                "synthetic_only": True,
                "simulation_only": True,
                "production_authority": False,
                "draft_auto_published": False,
                "performance_baseline_established": False,
                "p7_registration": None,
            },
        }
        report["report_fingerprint"] = _fingerprint(report)
        return report
    finally:
        shutil.rmtree(temporary_root, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report",
        type=Path,
        default=DEMO_ROOT / "build/validation/e2e-audit-demo-08.json",
    )
    arguments = parser.parse_args()
    try:
        report = build_report()
    except AuditFailure as error:
        print(json.dumps({"status": "FAIL", "check": str(error)}))
        return 1
    arguments.report.parent.mkdir(parents=True, exist_ok=True)
    arguments.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "report": str(arguments.report.resolve()),
                "assertions": len(report["main_flow"]["assertions"]),
                "wall_seconds": report["audit_wall_seconds"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
