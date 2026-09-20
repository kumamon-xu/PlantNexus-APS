"""Consumer integration over TCP against the formal Runtime composition."""

from collections.abc import Iterator
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace
import importlib.util
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
from threading import Event, Thread
from time import monotonic, sleep
from types import SimpleNamespace
from typing import Any

import pytest
import uvicorn

from app.api.app import create_runtime_app
from app.planning.policy.freeze_window import simulation_replan_policy
from backend.tests.integration import test_p9_events as event_support
from backend.tests.integration import test_p9_manual as manual
from backend.tests.integration.p9_consumers_support import (
    prepare_request,
    execute_request,
    second_version,
)

runtime = manual.runtime
events = event_support.events
ROOT = Path(__file__).resolve().parents[3]


def client_type() -> Any:
    spec = importlib.util.spec_from_file_location(
        "p9_host_client", ROOT / "examples/p9-headless-client/runtime_client.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.RuntimeClient


@contextmanager
def serve(application: Any) -> Iterator[str]:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(
        uvicorn.Config(application, log_level="error", lifespan="off")
    )
    thread = Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    try:
        deadline = monotonic() + 15
        while not server.started and thread.is_alive() and monotonic() < deadline:
            sleep(0.02)
        assert server.started
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=15)
        sock.close()
        assert not thread.is_alive()


@pytest.fixture
def consumer_runtime(events: Any, tmp_path: Path) -> Iterator[Any]:
    runtime = events.runtime
    runtime.identity.principal = replace(
        runtime.identity.principal,
        resolved_capabilities=frozenset(
            {
                "view",
                "edit",
                "lock",
                "approve",
                "reject",
                "publish",
                "export",
                "audit",
                "event_ingest",
                "event_view",
                "replan",
                "replan_view",
                "replan_control",
            }
        ),
    )
    policy_path = tmp_path / "consumer-policy.json"
    policy_path.write_text(json.dumps(simulation_replan_policy()), encoding="utf-8")
    settings = events.settings.model_copy(
        update={"runtime_replan_policy_path": policy_path}
    )
    app = create_runtime_app(settings, authorization_provider=runtime.identity)
    app.state.dynamic_replanning_clock = lambda: "2026-09-06T01:02:00Z"
    app.state.planning_workspace_clock = lambda: "2026-09-06T01:03:00Z"
    compared = second_version(runtime)
    with serve(app) as url:
        host = client_type()(url, "p9-test-token")
        host.command(
            manual.command(runtime.source, "APPROVE", key="p9-consumers-base-approve")
        )
        approved = host.version(runtime.source["schedule_version_id"])
        host.command(
            manual.command(
                approved,
                "PUBLISH",
                {"previous_current_version": None},
                key="p9-consumers-base-publish",
            )
        )
        base = host.version(approved["schedule_version_id"])
        document = event_support.event(events)
        document["occurred_at_utc"] = events.base.document["cutoff_at_utc"]
        document["received_at_utc"] = document["occurred_at_utc"]
        assignment = max(
            base["content"]["assignments"], key=lambda row: row["start_at_utc"]
        )
        document["payload"]["operation_id"] = assignment["operation_id"]
        document["payload"]["final_duration_seconds"] = (
            assignment["duration_ticks"] * 60 - 1
        )
        document["entity_refs"] = [
            {"entity_type": "OPERATION", "entity_id": assignment["operation_id"]}
        ]
        event_support._refresh_event_identity(document)
        yield SimpleNamespace(
            host=host,
            url=url,
            app=app,
            settings=settings,
            events=events,
            base=base,
            event=document,
            compared=compared,
        )


def test_host_event_replan_and_explicit_publication(consumer_runtime: Any) -> None:
    c = consumer_runtime
    from app.domain.workspace import (
        build_workspace_query_request,
        version_reference,
        WorkspaceView,
    )

    def read_query(view: Any) -> Any:
        return build_workspace_query_request(
            view=view,
            data_plane="SIMULATION",
            environment="TEST",
            synthetic=True,
            synthetic_provenance=c.base["synthetic_provenance"],
            correlation_id="p9-host-read-001",
            schedule_version_reference=version_reference(c.base),
        )

    read = c.host.request(
        "GET",
        f"/api/v1/schedule-versions/{c.base['schedule_version_id']}/workspace/ORDERS",
        query=read_query(WorkspaceView.ORDERS),
    )
    assert read["document"]["result"]["found"] is True
    comparison = c.host.request(
        "POST",
        "/api/v1/schedule-version-comparisons",
        read_query(WorkspaceView.VERSION_COMPARISON),
        compared_version=c.compared,
    )
    assert (
        comparison["comparison"]["base_version"]["schedule_version_id"]
        == c.base["schedule_version_id"]
    )
    assert c.host.submit(c.event, "p9-consumer-event-001")["replayed"] is False
    assert c.host.submit(c.event, "p9-consumer-event-001")["replayed"] is True
    document = prepare_request(c.events, c.base, c.event, c.app)
    accepted = c.host.submit(document, "p9-consumer-replan-001")
    assert accepted["result"]["attempt"]["state"] == "CREATED"
    from app.api.replanning_check import build_replan_action
    from app.data_validation.canonical_ingress import canonical_fingerprint

    original_attempt = accepted["result"]["attempt"]
    for action in ("CANCEL", "RETRY"):
        attempt = accepted["result"]["attempt"]
        key = f"p9-host-control-{action}"
        intent = build_replan_action(
            action=action,
            request_id=document["request_id"],
            request_fingerprint=document["request_fingerprint"],
            idempotency_key=key,
            correlation_id=f"p9-host-{action}",
        )
        intent.update(
            expected_attempt_id=attempt["attempt_id"],
            expected_attempt_number=attempt["attempt_number"],
            expected_planning_run_state=attempt["state"],
        )
        intent["action_fingerprint"] = canonical_fingerprint(
            {
                k: v
                for k, v in intent.items()
                if k not in {"action_id", "action_fingerprint"}
            }
        )
        intent["action_id"] = "replan-action-" + str(intent["action_fingerprint"])[7:]
        accepted = c.host.control(intent, key, document["planning_scope_id"])
        assert (
            c.host.control(intent, key, document["planning_scope_id"])["replayed"]
            is True
        )
    assert accepted["result"]["attempt"]["attempt_number"] == 2
    assert (
        accepted["result"]["attempt"]["planning_run_id"]
        != original_attempt["planning_run_id"]
    )
    execute_request(c.app, c.settings, accepted["result"]["attempt"])
    applied = c.app.state.dynamic_replanning_application.replan.lineage.get_applied_result_for_attempt(
        accepted["result"]["attempt"]["attempt_id"]
    )
    identity = applied.change_report["new_schedule_version"]["schedule_version_id"]
    candidate = c.host.version(identity)
    assert candidate["schedule_version_version"] == "schedule-version.v2"
    assert candidate["state"] == "DRAFT"
    for kind in ("SUBMIT_FOR_REVIEW", "APPROVE", "PUBLISH"):
        source = c.host.version(identity)
        payload = (
            {
                "previous_current_version": {
                    k: c.base[k]
                    for k in ("schedule_version_id", "state", "content_fingerprint")
                }
            }
            if kind == "PUBLISH"
            else {}
        )
        c.host.command(manual.command(source, kind, payload, key=f"p9-consumer-{kind}"))
    assert c.host.version(identity)["state"] == "PUBLISHED"
    assert c.host.version(c.base["schedule_version_id"])["state"] == "SUPERSEDED"


def test_host_manual_copy_on_write_and_stale_rejection(runtime: Any) -> None:
    with serve(runtime.app) as url:
        host = client_type()(url, "p9-test-token")
        original = deepcopy(runtime.source)
        command = manual.move(original, key="p9-consumer-manual-001")
        result = host.command(command)
        identity = result["new_version"]["schedule_version_id"]
        assert host.version(identity)["state"] == "DRAFT"
        assert (
            host.version(original["schedule_version_id"])["content_fingerprint"]
            == original["content_fingerprint"]
        )
        stale = manual.command(
            host.version(identity), "SUBMIT_FOR_REVIEW", key="p9-consumer-stale-001"
        )
        host.command(stale)
        stale["idempotency_key"] = "p9-consumer-stale-002"
        with pytest.raises(Exception, match="409"):
            host.command(stale)
        host.command(
            manual.command(
                host.version(identity), "APPROVE", key="p9-consumer-manual-approve"
            )
        )
        host.command(
            manual.command(
                host.version(identity),
                "PUBLISH",
                {"previous_current_version": None},
                key="p9-consumer-manual-publish",
            )
        )
        assert host.version(identity)["state"] == "PUBLISHED"
        unauthorized = client_type()(url, "invalid-test-token")
        with pytest.raises(Exception, match="401"):
            unauthorized.version(identity)


def test_unknown_server_capability_is_not_silently_dropped(runtime: Any) -> None:
    runtime.identity.principal = replace(
        runtime.identity.principal,
        resolved_capabilities=runtime.identity.principal.resolved_capabilities
        | {"unknown-capability"},
    )
    before = manual.counts(runtime)
    with serve(runtime.app) as url:
        host = client_type()(url, "p9-test-token")
        with pytest.raises(Exception, match="422: INVALID_REQUEST"):
            host.command(
                manual.command(runtime.source, "APPROVE", key="p9-unknown-capability")
            )
    assert manual.counts(runtime) == before


@pytest.mark.skipif(
    os.environ.get("P9_BROWSER") != "1", reason="Dedicated P9 Runtime browser command"
)
def test_browser_real_runtime(consumer_runtime: Any, tmp_path: Path) -> None:
    c = consumer_runtime
    exchange = tmp_path / "browser"
    exchange.mkdir()
    assignment = c.base["content"]["assignments"][-1]
    draft = c.host.command(
        manual.command(
            c.base,
            "SET_LOCK",
            {
                "lock": {
                    **{
                        k: assignment[k]
                        for k in (
                            "operation_id",
                            "resource_id",
                            "start_at_utc",
                            "end_at_utc",
                        )
                    },
                    "lock_id": "LOCK-P9-BROWSER",
                    "lock_type": "SOFT",
                }
            },
            key="p9-browser-manual-base",
        )
    )
    (exchange / "bootstrap.json").write_text(
        json.dumps(
            {
                "event": c.event,
                "base": c.base,
                "compared": c.compared,
                "manual": draft["new_version"],
                "assignment": assignment,
            }
        ),
        encoding="utf-8",
    )
    failures: list[BaseException] = []
    stopped = Event()

    def orchestrate() -> None:
        try:
            deadline = monotonic() + 90
            while not (exchange / "event-accepted").exists():
                if stopped.is_set():
                    return
                assert monotonic() < deadline, "Browser did not append the event"
                sleep(0.05)
            document = prepare_request(c.events, c.base, c.event, c.app)
            (exchange / "request.json").write_text(
                json.dumps(document), encoding="utf-8"
            )
            while not (exchange / "attempt.json").exists():
                if stopped.is_set():
                    return
                assert monotonic() < deadline, "Browser did not create the attempt"
                sleep(0.05)
            attempt = json.loads(
                (exchange / "attempt.json").read_text(encoding="utf-8")
            )
            execute_request(c.app, c.settings, attempt)
            applied = c.app.state.dynamic_replanning_application.replan.lineage.get_applied_result_for_attempt(
                attempt["attempt_id"]
            )
            (exchange / "completed.json").write_text(
                json.dumps(applied.change_report), encoding="utf-8"
            )
        except BaseException as error:
            failures.append(error)

    thread = Thread(target=orchestrate, daemon=True)
    thread.start()
    npm = shutil.which("npm")
    assert npm
    completed = subprocess.run(
        [
            npm,
            "exec",
            "--",
            "playwright",
            "test",
            "--config=playwright.p9-runtime.config.ts",
        ],
        cwd=ROOT / "frontend",
        env={**os.environ, "P9_RUNTIME_URL": c.url, "P9_EXCHANGE": str(exchange)},
        capture_output=True,
        text=True,
        timeout=150,
        encoding="utf-8",
        errors="replace",
    )
    stopped.set()
    thread.join(timeout=5)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert not failures, failures
