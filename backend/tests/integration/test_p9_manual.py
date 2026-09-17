"""P9-04: deployed Runtime HTTP -> fresh admission -> atomic repository owners."""

from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import sleep
from types import SimpleNamespace
from typing import Any

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, text

from app.api.app import create_runtime_app
from app.api.dependencies.authorization import PrincipalContext
from app.data_validation.canonical_ingress import (
    canonical_fingerprint,
    request_fingerprint,
)
from app.domain.workspace_contracts import workspace_command_fingerprint
from app.infrastructure.audit_repository import SqlAlchemyAuditRepository
from app.infrastructure.canonical_ingress_repository import (
    SqlAlchemyCanonicalIngressRepository,
)
from app.infrastructure.schedule_version_repository import (
    SqlAlchemyScheduleVersionRepository,
)
from app.infrastructure.workspace_persistence import WorkspaceDataPlane
from app.runtime_composition import compose_runtime, RuntimeProcess
from app.snapshots import import_package_id_for
from aps_extension_sdk import ValidationContext, ValidationOutput
from backend.tests.fixtures.p8_synthetic_extension import SyntheticValidationRule
from backend.tests.contract.p8_headless_http_support import (
    StaticAuthorizationProvider,
    authorization_policy,
    create_headers,
    HEADLESS_NOW,
)
from backend.tests.p8_runtime_support import (
    RecordingCelery,
    FixedRuntimeClock,
    dispatched_message,
    runtime_settings,
)
from backend.tests.p8_runtime_extension_support import runtime_extension_fixture
from backend.tests.p8_solver_worker_support import migrated_engine, worker_request
from backend.tests.security.test_p8_runtime_extension_security import (
    _RejectingValidationRule,
    VALIDATION_ID,
)


class WorkspaceIdentity:
    principal = PrincipalContext(
        actor_ref="actor:p9-manual-test",
        resolved_capabilities=frozenset(
            {"view", "edit", "lock", "approve", "reject", "publish", "export"}
        ),
        planning_run_scope=frozenset({"*"}),
        schedule_version_scope=frozenset({"*"}),
        export_job_scope=frozenset({"*"}),
        auth_policy_version="p9-simulation-policy.v1",
    )

    def resolve(self, bearer_token: str) -> PrincipalContext | None:
        return self.principal if bearer_token == "p9-test-token" else None


class ControlledValidation(_RejectingValidationRule):
    mode = "pass"

    def validate(self, context: ValidationContext) -> ValidationOutput:
        if self.mode == "reject":
            return _RejectingValidationRule.validate(self, context)
        if self.mode == "crash":
            raise RuntimeError("credential-do-not-leak")
        if self.mode == "timeout":
            sleep(0.2)
        return SyntheticValidationRule.validate(self, context)


def request_with_alternative_resource() -> dict[str, Any]:
    request = worker_request()
    records = request["payload"]["records"]
    # Move the fixed synthetic downtime into this fixture's planning horizon.
    downtime = records["calendars"][0]["unavailable_intervals"][0]
    downtime["start_at_utc"] = "2026-08-20T08:00:00Z"
    downtime["end_at_utc"] = "2026-08-20T09:00:00Z"
    resource = deepcopy(records["resources"][0])
    resource.update(resource_id="RESOURCE-002", resource_code="R002")
    resource["source"]["source_record_id"] = "SRC-RESOURCE-002"
    records["resources"].append(resource)
    option = deepcopy(records["routing_resource_options"][-1])
    option.update(
        routing_resource_option_id="ROUTING-OPTION-003", resource_id="RESOURCE-002"
    )
    option["source"]["source_record_id"] = "SRC-ROUTING-OPTION-003"
    records["routing_resource_options"].append(option)
    request["payload"]["package_id"] = import_package_id_for(request["payload"])
    request["payload_fingerprint"] = canonical_fingerprint(request["payload"])
    request["request_fingerprint"] = request_fingerprint(request)
    return request


@pytest.fixture
def runtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> Iterator[Any]:
    engine, _ = migrated_engine(tmp_path / "manual.db")
    url = str(engine.url)
    engine.dispose()
    extension = bool(getattr(request, "param", False))
    artifacts = ()
    ControlledValidation.mode = "pass"
    if extension:
        bundle = runtime_extension_fixture(
            tmp_path,
            database_url=url,
            overrides={VALIDATION_ID: ControlledValidation},
            invocation_timeout_ms=100,
        )
        settings, artifacts = bundle.settings, (bundle.artifact,)
    else:
        settings = runtime_settings(tmp_path, database_url=url)
    publisher = RecordingCelery()
    monkeypatch.setattr("app.runtime_composition._dispatch_client", lambda _: publisher)
    identity = WorkspaceIdentity()
    application = create_runtime_app(
        settings,
        authorization_provider=identity,
        host_identity_provider=StaticAuthorizationProvider(),
        host_authorization_policy=authorization_policy(),
        extension_artifacts=artifacts,
    )
    application.state.headless_clock = lambda: HEADLESS_NOW
    application.state.planning_workspace_clock = lambda: "2026-09-06T01:01:00Z"
    worker = compose_runtime(
        settings,
        process=RuntimeProcess.WORKER,
        extension_artifacts=artifacts,
        clock=FixedRuntimeClock(datetime(2026, 9, 6, 1, 0, 10, tzinfo=UTC)),
    )
    db = create_engine(url)
    schedules = SqlAlchemyScheduleVersionRepository(
        db, data_plane=WorkspaceDataPlane.SIMULATION
    )
    try:
        with TestClient(application) as client:
            document = request_with_alternative_resource()
            accepted = client.post(
                "/api/v1/planning-runs", json=document, headers=create_headers(document)
            )
            assert accepted.status_code == 202, accepted.text
            assert len(publisher.messages) == 1
            message = dispatched_message(publisher.messages[0])
            assert worker.worker is not None
            executed = worker.worker.execute(**message_arguments(message))
            assert executed.disposition.value == "COMPLETED"
            with db.connect() as connection:
                source_id = connection.scalar(
                    text("SELECT schedule_version_id FROM schedule_versions")
                )
            source = schedules.get(source_id)
            assert source is not None and source["state"] == "READY_FOR_REVIEW"
            yield SimpleNamespace(
                client=client,
                app=application,
                db=db,
                schedules=schedules,
                source=source,
                identity=identity,
                settings=settings,
                artifacts=artifacts,
            )
    finally:
        ControlledValidation.mode = "pass"
        worker.close()
        db.dispose()


def message_arguments(message: dict[str, object]) -> dict[str, Any]:
    return {k: message[k] for k in ("planning_run_id", "work_item_id", "worker_id")}


def command(
    source: dict[str, Any],
    kind: str,
    payload: dict[str, Any] | None = None,
    *,
    key: str = "p9-manual-command-0001",
) -> dict[str, Any]:
    capability = {
        "SET_LOCK": "lock",
        "REMOVE_LOCK": "lock",
        "APPROVE": "approve",
        "REJECT": "reject",
        "PUBLISH": "publish",
    }.get(kind, "edit")
    target = "SIMULATION_INTERNAL" if kind == "PUBLISH" else "WORKSPACE_INTERNAL"
    value = {
        "workspace_command_version": "workspace-command.v1",
        "schema_set_version": "2.6.0",
        "canonicalization_version": "canonical-json.v1",
        "command_id": f"command-{key}",
        "command_type": kind,
        "required_capability": capability,
        "idempotency_key": key,
        "idempotency_scope": f"SIMULATION/{kind}/{source['schedule_version_id']}/{target}",
        "request_fingerprint": "",
        "source_id": source["schedule_version_id"],
        "expected_state": source["state"],
        "expected_content_fingerprint": source["content_fingerprint"],
        "data_plane": "SIMULATION",
        "environment": source["environment"],
        "synthetic": True,
        "synthetic_provenance": source["synthetic_provenance"],
        "target": target,
        "reason": "Verify synthetic Runtime manual control.",
        "correlation_id": f"correlation-{key}",
        "payload": payload or {},
    }
    value["request_fingerprint"] = workspace_command_fingerprint(value)
    return value


def post(runtime: Any, value: dict[str, Any], *, token: str = "p9-test-token") -> Any:
    action = {
        "SUBMIT_FOR_REVIEW": "validate",
        "APPROVE": "approve",
        "REJECT": "reject",
        "PUBLISH": "publish",
    }.get(value["command_type"], "commands")
    return runtime.client.post(
        f"/api/v1/schedule-versions/{value['source_id']}/{action}",
        json=value,
        headers={
            "Authorization": f"Bearer {token}",
            "Idempotency-Key": value["idempotency_key"],
            "X-Correlation-Id": value["correlation_id"],
        },
    )


def move(source: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    assignment = source["content"]["assignments"][-1]
    payload = {
        k: assignment[k]
        for k in ("operation_id", "resource_id", "start_at_utc", "end_at_utc")
    }
    for field in ("start_at_utc", "end_at_utc"):
        payload[field] = (
            (
                datetime.fromisoformat(payload[field].replace("Z", "+00:00"))
                + timedelta(minutes=10)
            )
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z")
        )
    return command(source, "MOVE_OPERATION", payload, **kwargs)


def counts(runtime: Any) -> tuple[int, ...]:
    with runtime.db.connect() as connection:
        return tuple(
            connection.scalar(text(f"SELECT count(*) FROM {table}"))
            for table in ("schedule_versions", "audit_events")
        )


def result_source(runtime: Any, response: Any) -> dict[str, Any]:
    assert response.status_code == 200, response.text
    return runtime.schedules.get(response.json()["new_version"]["schedule_version_id"])


def test_runtime_manual_move_submit_reject_and_exact_replay(runtime: Any) -> None:
    original = deepcopy(runtime.source)
    value = move(original)
    draft = result_source(runtime, post(runtime, value))
    assert (
        draft["state"] == "DRAFT"
        and draft["schedule_version_id"] != original["schedule_version_id"]
    )
    assert runtime.schedules.get(original["schedule_version_id"]) == original
    before = counts(runtime)
    replay = post(runtime, value)
    assert replay.status_code == 200 and replay.json()["exact_replay"] is True
    assert counts(runtime) == before
    ready = result_source(
        runtime,
        post(runtime, command(draft, "SUBMIT_FOR_REVIEW", key="p9-submit-command-001")),
    )
    assert (
        ready["state"] == "READY_FOR_REVIEW"
        and ready["content_fingerprint"] == draft["content_fingerprint"]
    )
    rejected = result_source(
        runtime, post(runtime, command(ready, "REJECT", key="p9-reject-command-001"))
    )
    assert rejected["state"] == "REJECTED"
    assert (
        post(
            runtime,
            command(
                rejected,
                "PUBLISH",
                {"previous_current_version": None},
                key="p9-no-publish-00001",
            ),
        ).status_code
        == 409
    )


def test_runtime_assigns_an_alternative_resource(runtime: Any) -> None:
    assignment = runtime.source["content"]["assignments"][-1]
    alternative = (
        "RESOURCE-002"
        if assignment["resource_id"] == "RESOURCE-001"
        else "RESOURCE-001"
    )
    draft = result_source(
        runtime,
        post(
            runtime,
            command(
                runtime.source,
                "ASSIGN_RESOURCE",
                {
                    "operation_id": assignment["operation_id"],
                    "resource_id": alternative,
                },
            ),
        ),
    )
    assert draft["content"]["assignments"][-1]["resource_id"] == alternative


@pytest.mark.parametrize("kind", ["HARD", "SOFT"])
def test_runtime_lock_remove_and_hard_lock_guard(runtime: Any, kind: str) -> None:
    assignment = runtime.source["content"]["assignments"][-1]
    lock = {
        k: assignment[k]
        for k in ("operation_id", "resource_id", "start_at_utc", "end_at_utc")
    }
    lock.update(lock_id="LOCK-P9-MANUAL", lock_type=kind)
    locked = result_source(
        runtime, post(runtime, command(runtime.source, "SET_LOCK", {"lock": lock}))
    )
    if kind == "HARD":
        before = counts(runtime)
        assert post(runtime, move(locked, key="p9-hard-move-denied")).status_code == 409
        assert counts(runtime) == before
    unlocked = result_source(
        runtime,
        post(
            runtime,
            command(
                locked,
                "REMOVE_LOCK",
                {"lock_id": lock["lock_id"], "operation_id": lock["operation_id"]},
                key="p9-remove-lock-0001",
            ),
        ),
    )
    assert all(v["lock_id"] != lock["lock_id"] for v in unlocked["content"]["locks"])


@pytest.mark.parametrize(
    "failure,status",
    [
        ("token", 401),
        ("capability", 403),
        ("scope", 403),
        ("stale", 409),
        ("conflict", 409),
        ("invalid", 422),
    ],
)
def test_runtime_manual_rejects_without_partial_version(
    runtime: Any, failure: str, status: int
) -> None:
    value = move(runtime.source)
    if failure == "capability":
        runtime.identity.principal = replace(
            runtime.identity.principal, resolved_capabilities=frozenset({"view"})
        )
    if failure == "scope":
        runtime.identity.principal = replace(
            runtime.identity.principal,
            schedule_version_scope=frozenset({"another-version"}),
        )
    if failure == "conflict":
        assert post(runtime, value).status_code == 200
        value["reason"] = "Different synthetic request with the same key."
    if failure == "stale":
        value["expected_content_fingerprint"] = "sha256:" + "0" * 64
    if failure == "invalid":
        value["payload"]["resource_id"] = "RESOURCE-UNKNOWN"
    value["request_fingerprint"] = workspace_command_fingerprint(value)
    before = counts(runtime)
    response = post(
        runtime, value, token="invalid" if failure == "token" else "p9-test-token"
    )
    assert response.status_code == status, response.text
    assert counts(runtime) == before
    assert (
        runtime.schedules.get(runtime.source["schedule_version_id"]) == runtime.source
    )


def test_runtime_core_calendar_violation_fails_before_write(runtime: Any) -> None:
    assignment = runtime.source["content"]["assignments"][-1]
    duration = datetime.fromisoformat(
        assignment["end_at_utc"]
    ) - datetime.fromisoformat(assignment["start_at_utc"])
    start = datetime(2026, 8, 20, 8, tzinfo=UTC)
    payload = {
        "operation_id": assignment["operation_id"],
        "resource_id": assignment["resource_id"],
        "start_at_utc": start.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "end_at_utc": (start + duration)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
    }
    before = counts(runtime)
    response = post(runtime, command(runtime.source, "MOVE_OPERATION", payload))
    assert response.status_code == 422, response.text
    assert response.json()["details"]["reason"] == "VALIDATION_FAILED"
    assert counts(runtime) == before


def test_runtime_submit_concurrent_single_winner(runtime: Any) -> None:
    draft = result_source(runtime, post(runtime, move(runtime.source)))
    values = [
        command(draft, "SUBMIT_FOR_REVIEW", key=f"p9-concurrent-submit-{i:02}")
        for i in range(2)
    ]
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda value: post(runtime, value), values))
    assert sorted(r.status_code for r in responses) == [200, 409]
    assert (
        runtime.schedules.get(draft["schedule_version_id"])["state"]
        == "READY_FOR_REVIEW"
    )


def test_runtime_manual_audit_failure_rolls_back(
    runtime: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("credential-do-not-leak")

    monkeypatch.setattr(SqlAlchemyAuditRepository, "append_in_transaction", fail)
    before = counts(runtime)
    response = post(runtime, move(runtime.source))
    assert response.status_code == 500 and "credential-do-not-leak" not in response.text
    assert counts(runtime) == before


def test_runtime_submit_audit_failure_rolls_back(
    runtime: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    draft = result_source(runtime, post(runtime, move(runtime.source)))

    def fail(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("credential-do-not-leak")

    monkeypatch.setattr(SqlAlchemyAuditRepository, "append_in_transaction", fail)
    before = counts(runtime)
    response = post(
        runtime, command(draft, "SUBMIT_FOR_REVIEW", key="p9-submit-rollback-001")
    )
    assert response.status_code == 500 and "credential-do-not-leak" not in response.text
    assert counts(runtime) == before
    assert runtime.schedules.get(draft["schedule_version_id"]) == draft


def test_runtime_restart_approval_publication_and_published_copy_on_write(
    runtime: Any,
) -> None:
    draft = result_source(runtime, post(runtime, move(runtime.source)))
    # A separately composed API must recover the command owner from durable lineage.
    restarted = create_runtime_app(
        runtime.settings,
        authorization_provider=runtime.identity,
        extension_artifacts=(),
    )
    restarted.state.planning_workspace_clock = lambda: "2026-09-06T01:02:00Z"
    with TestClient(restarted) as client:
        original_client, runtime.client = runtime.client, client
        try:
            ready = result_source(
                runtime,
                post(
                    runtime,
                    command(draft, "SUBMIT_FOR_REVIEW", key="p9-restart-submit-001"),
                ),
            )
            approved = result_source(
                runtime,
                post(runtime, command(ready, "APPROVE", key="p9-restart-approve-001")),
            )
            published_response = post(
                runtime,
                command(
                    approved,
                    "PUBLISH",
                    {"previous_current_version": None},
                    key="p9-restart-publish-001",
                ),
            )
            assert published_response.status_code == 200, published_response.text
            published = runtime.schedules.get(approved["schedule_version_id"])
            assert published["state"] == "PUBLISHED"
            edited = result_source(
                runtime, post(runtime, move(published, key="p9-published-edit-001"))
            )
            assert (
                edited["state"] == "DRAFT"
                and edited["schedule_version_id"] != published["schedule_version_id"]
            )
            assert runtime.schedules.get(published["schedule_version_id"]) == published
        finally:
            runtime.client = original_client


def test_runtime_missing_problem_fails_before_write(
    runtime: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        SqlAlchemyCanonicalIngressRepository,
        "get_by_planning_run_id",
        lambda *args: None,
    )
    before = counts(runtime)
    response = post(runtime, move(runtime.source))
    assert (
        response.status_code == 422
        and response.json()["details"]["reason"] == "MIXED_LINEAGE"
    )
    assert counts(runtime) == before


def test_runtime_identity_change_requires_reassessment(runtime: Any) -> None:
    settings = runtime.settings.model_copy(
        update={"runtime_artifact_fingerprint": "sha256:" + "9" * 64}
    )
    changed = create_runtime_app(
        settings, authorization_provider=runtime.identity, extension_artifacts=()
    )
    changed.state.planning_workspace_clock = lambda: "2026-09-06T01:02:00Z"
    before = counts(runtime)
    with TestClient(changed) as client:
        original_client, runtime.client = runtime.client, client
        try:
            response = post(runtime, move(runtime.source))
            assert response.status_code == 409, response.text
            assert counts(runtime) == before
        finally:
            runtime.client = original_client


def test_runtime_replan_version_is_never_downgraded_to_v1(runtime: Any) -> None:
    from app.application.replan_application_check import (
        build_replan_application_fixture,
        seed_replan_application_runtime,
    )

    from backend.tests.p8_solver_worker_support import ROOT as root

    fixture = build_replan_application_fixture(root)
    replan = seed_replan_application_runtime(root, runtime.db, fixture)
    source = replan.service.execute(fixture.input, fixture.context).schedule_version
    assert source is not None
    before = counts(runtime)
    response = post(runtime, command(source, "SUBMIT_FOR_REVIEW"))
    assert response.status_code == 422, response.text
    assert response.json()["details"] == {
        "field": "source.schedule_version_version",
        "reason": "MIXED_LINEAGE",
    }
    assert (
        counts(runtime) == before
        and runtime.schedules.get(source["schedule_version_id"]) == source
    )


@pytest.mark.parametrize("runtime", [True], indirect=True)
@pytest.mark.parametrize(
    "mode,status", [("pass", 200), ("reject", 422), ("crash", 503), ("timeout", 503)]
)
@pytest.mark.parametrize("stage", ["manual", "submit"])
def test_runtime_manual_real_extension_admission(
    runtime: Any, stage: str, mode: str, status: int
) -> None:
    source = runtime.source
    if stage == "submit":
        source = result_source(runtime, post(runtime, move(source)))
    value = (
        move(source, key="p9-extension-manual-001")
        if stage == "manual"
        else command(source, "SUBMIT_FOR_REVIEW", key="p9-extension-submit-001")
    )
    ControlledValidation.mode = mode
    before = counts(runtime)
    response = post(runtime, value)
    assert response.status_code == status, response.text
    assert "credential-do-not-leak" not in response.text
    if status != 200:
        assert counts(runtime) == before
        assert runtime.schedules.get(source["schedule_version_id"]) == source
