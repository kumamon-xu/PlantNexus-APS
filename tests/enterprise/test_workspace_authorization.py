from copy import deepcopy
import json
from pathlib import Path

import pytest

from infra.enterprise.bootstrap import preflight, workspace
from tests.enterprise.configuration_fixtures import CANARY, write_env


def audit_sink(path):
    return workspace.DurableDenialAudit(
        path,
        policy_id="enterprise-workspace-test.v1",
        policy_fingerprint="sha256:" + "a" * 64,
    )


def policy(directory):
    token = directory / "workspace-token"
    token.write_text(CANARY + "-separate-workspace", encoding="utf-8")
    return {
        "policy_version": "enterprise-workspace-authorization.v1",
        "policy_id": "enterprise-workspace-test.v1",
        "environment": "TEST",
        "data_plane": "SIMULATION",
        "production_binding": False,
        "principals": [
            {
                "actor_ref": "actor:workspace-test",
                "token_file": str(token),
                "capabilities": ["view"],
                "allow_all_synthetic_resources": False,
                "planning_run_scope": [],
                "schedule_version_scope": ["synthetic-allowed"],
                "export_job_scope": [],
            }
        ],
    }


def test_separate_identity_and_explicit_resource_capabilities(configured):
    directory, env = configured
    doc = policy(directory)
    Path(env["WORKSPACE_AUTHORIZATION_POLICY_FILE"]).write_text(
        json.dumps(doc), encoding="utf-8"
    )
    p = preflight.prepare(write_env(directory, env))
    provider = workspace.LocalWorkspaceIdentity(p.workspace_policy, p.workspace_tokens)
    assert provider.resolve(p.token) is None
    assert provider.resolve("unknown") is None
    principal = provider.resolve(CANARY + "-separate-workspace")
    assert principal is not None
    assert principal.resolved_capabilities == frozenset({"view"})
    assert principal.schedule_version_scope == frozenset({"synthetic-allowed"})
    assert not principal.export_job_scope and not principal.production_binding
    assert CANARY not in json.dumps(p.report())
    before = p.report()["nonsecret_configuration_fingerprint"]
    doc["principals"][0]["capabilities"] = ["view", "approve"]
    Path(env["WORKSPACE_AUTHORIZATION_POLICY_FILE"]).write_text(
        json.dumps(doc), encoding="utf-8"
    )
    changed = preflight.prepare(write_env(directory, env))
    assert changed.report()["nonsecret_configuration_fingerprint"] != before


@pytest.mark.parametrize(
    "mutation",
    [
        "production",
        "binding",
        "unknown",
        "wildcard",
        "glob",
        "duplicate",
        "capability",
        "same-token",
    ],
)
def test_invalid_policy_fails_closed_before_runtime(configured, mutation):
    directory, env = configured
    doc = policy(directory)
    p = doc["principals"][0]
    if mutation == "production":
        doc["environment"] = "PRODUCTION"
    if mutation == "binding":
        doc["production_binding"] = True
    if mutation == "unknown":
        p["role"] = "administrator"
    if mutation == "wildcard":
        p["schedule_version_scope"] = ["*"]
    if mutation == "glob":
        p["schedule_version_scope"] = ["synthetic-*"]
    if mutation == "duplicate":
        doc["principals"].append(deepcopy(p))
    if mutation == "capability":
        p["capabilities"] = ["admin"]
    if mutation == "same-token":
        p["token_file"] = env["IDENTITY_TOKEN_FILE"]
    Path(env["WORKSPACE_AUTHORIZATION_POLICY_FILE"]).write_text(
        json.dumps(doc), encoding="utf-8"
    )
    with pytest.raises(preflight.BootstrapError):
        preflight.prepare(write_env(directory, env))


def test_denial_audit_is_durable_redacted_and_append_only(tmp_path):
    from app.api.dependencies.authorization import AuthorizationAuditRecord

    path = tmp_path / "audit.jsonl"
    sink = audit_sink(path)
    event = AuthorizationAuditRecord(
        CANARY,
        CANARY,
        "approve",
        "SCHEDULE_VERSION",
        CANARY,
        "DENIED",
        "CAPABILITY_DENIED",
        "SIMULATION",
        "TEST",
    )
    sink.record(event)
    first = path.read_bytes()
    audit_sink(path).record(event)
    assert path.read_bytes().startswith(first)
    rows = [json.loads(line) for line in path.read_bytes().splitlines()]
    assert len(rows) == 2 and CANARY.encode() not in path.read_bytes()
    assert rows[0]["required_capability"] == "approve"
    assert rows[0]["reason"] == "CAPABILITY_DENIED"
    assert rows[0]["policy_id"] == "enterprise-workspace-test.v1"
    assert rows[0]["policy_fingerprint"] == "sha256:" + "a" * 64
    with pytest.raises(OSError):
        audit_sink(tmp_path / "absent" / "audit.jsonl")


def test_http_capability_and_scope_denials_use_durable_sink(tmp_path):
    from fastapi.testclient import TestClient
    from app.api.app import create_app
    from app.infrastructure.config import Settings, RuntimeEnvironment, DataPlane

    p = policy(tmp_path)
    provider = workspace.LocalWorkspaceIdentity(
        workspace.validate(p), (CANARY + "-separate-workspace",)
    )
    sink = audit_sink(tmp_path / "denials.jsonl")
    app = create_app(
        Settings(
            runtime_environment=RuntimeEnvironment.TEST,
            data_plane=DataPlane.SIMULATION,
            simulation_api_enabled=True,
        ),
        authorization_provider=provider,
        authorization_audit_sink=sink,
    )
    with TestClient(app) as client:
        assert (
            client.get("/api/v1/schedule-versions/synthetic-forbidden").status_code
            == 401
        )
        headers = {"Authorization": "Bearer " + CANARY + "-separate-workspace"}
        assert (
            client.get(
                "/api/v1/schedule-versions/synthetic-forbidden", headers=headers
            ).status_code
            == 403
        )
        assert (
            client.get(
                "/api/v1/export-jobs/synthetic-forbidden/download", headers=headers
            ).status_code
            == 403
        )
    rows = [json.loads(line) for line in sink.path.read_bytes().splitlines()]
    assert [r["reason"] for r in rows] == [
        "AUTHENTICATION_REQUIRED",
        "RESOURCE_SCOPE_DENIED",
        "CAPABILITY_DENIED",
    ]


def test_audit_storage_failure_blocks_http_application(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app.api.app import create_app
    from app.infrastructure.config import Settings, RuntimeEnvironment, DataPlane

    sink = audit_sink(tmp_path / "audit.jsonl")

    def fail(_):
        raise OSError("synthetic storage unavailable")

    monkeypatch.setattr(workspace.os, "fsync", fail)
    app = create_app(
        Settings(
            runtime_environment=RuntimeEnvironment.TEST,
            data_plane=DataPlane.SIMULATION,
            simulation_api_enabled=True,
        ),
        authorization_audit_sink=sink,
    )
    with TestClient(app) as client:
        response = client.get("/api/v1/schedule-versions/synthetic-unknown")
    assert response.status_code == 500
    assert "synthetic storage unavailable" not in response.text
