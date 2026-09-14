"""Build-side synthetic inputs. Only generated files enter the clean consumer."""

import json


def write(path, value):
    path.write_text(
        json.dumps(value, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
        newline="\n",
    )


def create(directory):
    from infra.enterprise.compose.verify_container import fixture
    from tests.enterprise.configuration_fixtures import (
        add_extension,
        write_env,
        container_readable_fixture,
        CANARY,
    )
    from backend.tests.p8_solver_worker_support import (
        worker_request,
        planning_policy,
        solve_limits,
    )
    from backend.tests.p8_runtime_support import runtime_http_policy
    from app.application.host_authorization import HEADLESS_OPERATION_CAPABILITIES

    config, secrets, env = fixture(directory)
    request = worker_request()
    write(config / "planning-policy.json", planning_policy())
    write(config / "solve-limits.json", solve_limits())
    write(
        config / "http-policy.json",
        runtime_http_policy(
            extension_facts={
                "extension_facts_version": "runtime-extension-facts.v1",
                "resource_attributes": {"RESOURCE-001": {"tags": ["alpha-qualified"]}},
                "operation_attributes": {},
                "events": [],
                "publication_authority_reference": "authority.p8.acceptance.synthetic",
            }
        ),
    )
    auth = json.loads((config / "authorization.json").read_text(encoding="utf-8"))
    auth["principals"][0]["operations"] = list(HEADLESS_OPERATION_CAPABILITIES)
    auth["principals"][0]["scopes"] = [
        {
            k: request["requested_scope"][k]
            for k in ("tenant_id", "factory_id", "planning_scope_id")
        }
    ]
    write(config / "authorization.json", auth)
    add_extension(config, env, container_paths=True)
    env = {k: v.replace("/case/", "/etc/plantnexus/") for k, v in env.items()}
    (secrets / "extension_key").write_bytes((config / "extension-key").read_bytes())
    (config / "extension-key").unlink()
    env["EXTENSION_KEY_FILE"] = "/run/secrets/extension_key"
    p = config / "extension-lock.json"
    p.write_text(
        p.read_text(encoding="utf-8").replace("/case/", "/etc/plantnexus/"),
        encoding="utf-8",
        newline="\n",
    )
    policy = json.loads(
        (config / "workspace-authorization.json").read_text(encoding="utf-8")
    )
    for name, capabilities, scope in [
        ("operator", ["view", "approve", "publish", "export", "audit"], ["*"]),
        ("limited", ["view"], []),
    ]:
        (secrets / ("workspace_" + name)).write_text(
            CANARY + "-workspace-" + name, encoding="utf-8", newline="\n"
        )
        policy["principals"].append(
            {
                "actor_ref": "actor:workspace-test-" + name,
                "token_file": "/run/secrets/workspace_" + name,
                "capabilities": capabilities,
                "allow_all_synthetic_resources": bool(scope),
                "planning_run_scope": scope,
                "schedule_version_scope": scope,
                "export_job_scope": scope,
            }
        )
    write(config / "workspace-authorization.json", policy)
    write_env(config, env)
    container_readable_fixture(secrets)
    return request


def workspace_command(schedule, command_type, capability, target, key, payload):
    from app.domain.workspace_contracts import workspace_command_fingerprint

    value = {
        "workspace_command_version": "workspace-command.v1",
        "schema_set_version": "2.6.0",
        "canonicalization_version": "canonical-json.v1",
        "command_id": "command-" + key,
        "command_type": command_type,
        "required_capability": capability,
        "idempotency_key": key,
        "idempotency_scope": f"SIMULATION/{command_type}/{schedule['schedule_version_id']}/{target}",
        "source_id": schedule["schedule_version_id"],
        "expected_state": schedule["state"],
        "expected_content_fingerprint": schedule["content_fingerprint"],
        "data_plane": "SIMULATION",
        "environment": schedule["environment"],
        "synthetic": True,
        "synthetic_provenance": schedule["synthetic_provenance"],
        "target": target,
        "reason": "Execute explicit synthetic clean offline acceptance.",
        "correlation_id": "correlation-" + key,
        "payload": payload,
        "request_fingerprint": "sha256:" + "0" * 64,
    }
    value["request_fingerprint"] = workspace_command_fingerprint(value)
    return value
