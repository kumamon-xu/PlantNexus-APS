"""DEMO-AUTH/API: cookie bootstrap, job recovery surface, and story flow."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from pydantic import SecretStr
import pytest

from app.api.app import create_app
from app.api.replanning_contracts import (
    DynamicReplanningApplicationError,
    DynamicReplanningApplicationRequest,
    DynamicReplanningOperation,
    DynamicReplanningRequestContext,
)
from app.infrastructure.config import DataPlane, RuntimeEnvironment, Settings

from plantnexus_demo.composition import create_demo_app
from plantnexus_demo.security import SimulationLocalAuthorizationProvider


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_demo_http_flow_is_cookie_authenticated_and_token_safe(tmp_path: Path) -> None:
    application = create_demo_app(
        repository_root=REPOSITORY_ROOT,
        runtime_root=tmp_path / "runtime",
        auto_resume_queued=False,
    )
    runtime = application.state.demo_runtime
    with TestClient(application) as client:
        unauthenticated = client.get("/api/demo/v1/bootstrap")
        assert unauthenticated.status_code == 401

        session = client.post("/api/demo/v1/session")
        assert session.status_code == 200
        assert runtime.local_token not in session.text
        empty = client.get("/api/demo/v1/bootstrap")
        assert empty.status_code == 200
        assert empty.json()["story_state"] == "EMPTY"

        reset = client.post(
            "/api/demo/v1/resets",
            headers={"Idempotency-Key": "demo-api-reset-idempotency-0001"},
            json={
                "request_version": "cnc-demo-reset-request.v1",
                "profile_name": "smoke",
            },
        )
        assert reset.status_code == 202
        reset_job = runtime.runner.wait(reset.json()["job_id"], timeout=30)
        assert reset_job.status == "SUCCEEDED"
        run_id = reset_job.result["run_id"]
        with pytest.raises(DynamicReplanningApplicationError) as missing_event:
            application.state.dynamic_replanning_application.execute(
                DynamicReplanningApplicationRequest(
                    operation=DynamicReplanningOperation.GET_EXECUTION_EVENT,
                    context=DynamicReplanningRequestContext(
                        correlation_id="correlation-demo-p4-configured",
                        actor_ref="actor:cnc-demo-presenter",
                        authenticated=True,
                        resolved_capabilities=frozenset({"event_view"}),
                        planning_scope_scope=frozenset({"*"}),
                        auth_policy_version="demo-local-simulation-auth.v1",
                        production_binding=False,
                        occurred_at_utc="2026-09-02T08:00:00Z",
                        code_commit="uncommitted",
                        data_plane="SIMULATION",
                        environment="TEST",
                    ),
                    resource_id="execution-event-" + "0" * 64,
                    planning_scope_id="CNC-DEMO-SHOWCASE",
                )
            )
        assert missing_event.value.reason == "NOT_FOUND"
        reset_replay = client.post(
            "/api/demo/v1/resets",
            headers={"Idempotency-Key": "demo-api-reset-idempotency-0001"},
            json={
                "request_version": "cnc-demo-reset-request.v1",
                "profile_name": "smoke",
            },
        )
        assert reset_replay.status_code == 202
        assert reset_replay.json()["job_id"] == reset_job.job_id
        assert reset_replay.json()["status"] == "SUCCEEDED"
        assert reset_replay.json()["replayed"] is True

        plan = client.post(
            "/api/demo/v1/initial-plans",
            headers={"Idempotency-Key": "demo-api-plan-idempotency-0001"},
            json={
                "request_version": "cnc-demo-initial-plan-request.v1",
                "expected_run_id": run_id,
            },
        )
        assert plan.status_code == 202
        plan_job = runtime.runner.wait(plan.json()["job_id"], timeout=30)
        assert plan_job.status == "SUCCEEDED"
        assert plan_job.result is not None
        version_id = plan_job.result["schedule_version_id"]
        content_fingerprint = plan_job.result["content_fingerprint"]
        plan_replay = client.post(
            "/api/demo/v1/initial-plans",
            headers={"Idempotency-Key": "demo-api-plan-idempotency-0001"},
            json={
                "request_version": "cnc-demo-initial-plan-request.v1",
                "expected_run_id": run_id,
            },
        )
        assert plan_replay.status_code == 202
        assert plan_replay.json()["job_id"] == plan_job.job_id
        assert plan_replay.json()["status"] == "SUCCEEDED"
        assert plan_replay.json()["replayed"] is True
        assert client.get("/api/demo/v1/state").json()["story_state"] == (
            "READY_FOR_REVIEW"
        )

        activation = client.post(
            "/api/demo/v1/baseline-activations",
            headers={"Idempotency-Key": "demo-api-activate-idempotency-0001"},
            json={
                "command_version": "cnc-demo-baseline-activation.v1",
                "expected_run_id": run_id,
                "schedule_version_id": version_id,
                "content_fingerprint": content_fingerprint,
                "expected_state_revision": 1,
                "confirmation": "ACTIVATE_SIMULATION_BASELINE",
            },
        )
        assert activation.status_code == 200, activation.text
        assert activation.json()["state"] == "PUBLISHED"
        final_state = client.get("/api/demo/v1/state")
        assert final_state.json()["story_state"] == "BASELINE_PUBLISHED"
        assert runtime.local_token not in final_state.text

        urgent = client.post(
            "/api/demo/v1/urgent-orders",
            headers={"Idempotency-Key": "demo-api-urgent-idempotency-0001"},
            json={
                "command_version": "cnc-demo-urgent-order-command.v1",
                "expected_run_id": run_id,
                "expected_base_version_id": version_id,
                "route_template_id": "CNC-ROUTE-4",
                "quantity": 4,
                "due_at_local": "2026-09-09T18:00:00",
                "priority_class": "URGENT",
                "note": "API 演示加急订单",
            },
        )
        assert urgent.status_code == 202, urgent.text
        urgent_job = runtime.runner.wait(urgent.json()["job_id"], timeout=45)
        assert urgent_job.status == "SUCCEEDED"
        assert urgent_job.result is not None
        assert urgent_job.result["schedule_state"] == "DRAFT"
        assert urgent_job.result["current_published_version_id"] == version_id
        assert [stage["stage"] for stage in runtime.control.job_stages(urgent_job.job_id)] == [
            "PREPARING_IMPORT",
            "IMPORTING_URGENT_DEMAND",
            "APPENDING_EVENT",
            "PROJECTING_FACTS",
            "CREATING_REQUEST",
            "SOLVING",
            "VERIFYING_SOLUTION",
            "COMMITTING_RESULT",
            "BUILDING_PRESENTATION",
            "COMPLETE",
        ]
        comparison_state = client.get("/api/demo/v1/state")
        assert comparison_state.json()["story_state"] == "DRAFT_COMPARISON_READY"
        assert comparison_state.json()["current_publication"][
            "schedule_version_id"
        ] == version_id
        urgent_replay = client.post(
            "/api/demo/v1/urgent-orders",
            headers={"Idempotency-Key": "demo-api-urgent-idempotency-0001"},
            json={
                "command_version": "cnc-demo-urgent-order-command.v1",
                "expected_run_id": run_id,
                "expected_base_version_id": version_id,
                "route_template_id": "CNC-ROUTE-4",
                "quantity": 4,
                "due_at_local": "2026-09-09T18:00:00",
                "priority_class": "URGENT",
                "note": "API 演示加急订单",
            },
        )
        assert urgent_replay.status_code == 202
        assert urgent_replay.json()["job_id"] == urgent_job.job_id
        assert urgent_replay.json()["replayed"] is True


def test_wrong_token_and_missing_capability_fail_closed(tmp_path: Path) -> None:
    application = create_demo_app(
        repository_root=REPOSITORY_ROOT,
        runtime_root=tmp_path / "runtime",
        auto_resume_queued=False,
    )
    runtime = application.state.demo_runtime
    with TestClient(application) as client:
        wrong = client.get(
            "/api/demo/v1/bootstrap",
            headers={"Authorization": "Bearer definitely-wrong"},
        )
        assert wrong.status_code == 401
        assert "definitely-wrong" not in wrong.text

        application.state.authorization_provider = SimulationLocalAuthorizationProvider(
            runtime.local_token,
            capabilities=frozenset({"view"}),
        )
        denied = client.post(
            "/api/demo/v1/resets",
            headers={
                "Authorization": f"Bearer {runtime.local_token}",
                "Idempotency-Key": "demo-api-denied-idempotency-0001",
            },
            json={
                "request_version": "cnc-demo-reset-request.v1",
                "profile_name": "smoke",
            },
        )
        assert denied.status_code == 403
        assert runtime.local_token not in denied.text


def test_wrong_schedule_scope_and_production_plane_fail_closed(tmp_path: Path) -> None:
    application = create_demo_app(
        repository_root=REPOSITORY_ROOT,
        runtime_root=tmp_path / "runtime",
        auto_resume_queued=False,
    )
    runtime = application.state.demo_runtime
    application.state.authorization_provider = SimulationLocalAuthorizationProvider(
        runtime.local_token,
        capabilities=frozenset({"view"}),
        schedule_version_scope=frozenset({"schedule-version-in-scope"}),
    )
    with TestClient(application) as client:
        denied_scope = client.get(
            "/api/v1/schedule-versions/schedule-version-out-of-scope",
            headers={"Authorization": f"Bearer {runtime.local_token}"},
        )
    assert denied_scope.status_code == 403
    assert runtime.local_token not in denied_scope.text

    production = create_app(
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
        authorization_provider=SimulationLocalAuthorizationProvider(
            "production-must-never-resolve-this-token"
        ),
    )
    with TestClient(production) as client:
        denied_production = client.get(
            "/api/v1/schedule-versions/schedule-version-production",
            headers={"Authorization": "Bearer production-must-never-resolve-this-token"},
        )
    assert denied_production.status_code == 403
    assert "production-must-never-resolve-this-token" not in denied_production.text
