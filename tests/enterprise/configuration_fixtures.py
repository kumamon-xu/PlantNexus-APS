"""Synthetic files for deployment preflight tests; never customer configuration."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
CANARY = "P8-24-SYNTHETIC-CANARY-NEVER-A-REAL-SECRET-884290"


def create_fixture(directory: Path, *, container_paths: bool = False) -> dict[str, str]:
    directory.mkdir(parents=True, exist_ok=True)

    def path(name):
        return "/case/" + name if container_paths else str((directory / name).resolve())

    for name, value in (
        ("db-user", "syntheticuser"),
        ("redis-user", "default"),
        ("password", CANARY),
        ("identity-token", CANARY + "-token"),
    ):
        (directory / name).write_text(value, encoding="utf-8")
    (directory / "openssl.cnf").write_text(
        "[req]\ndistinguished_name=dn\n[dn]\n", encoding="ascii"
    )
    subprocess.run(
        [
            "openssl",
            "req",
            "-config",
            str(directory / "openssl.cnf"),
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-days",
            "1",
            "-subj",
            "/CN=aps.example.invalid",
            "-keyout",
            str(directory / "tls.key"),
            "-out",
            str(directory / "tls.crt"),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for name in ("planning-policy", "solve-limits"):
        (directory / (name + ".json")).write_bytes(
            (ROOT / "schemas/samples" / (name + ".v1.synthetic.json")).read_bytes()
        )
    http = json.loads(
        (ROOT / "infra/operations/runtime-http-policy.v2.json").read_text(
            encoding="utf-8"
        )
    )
    (directory / "http-policy.json").write_text(json.dumps(http), encoding="utf-8")
    scope = {
        k: http["scopes"][0][k]
        for k in ("tenant_id", "factory_id", "planning_scope_id")
    }
    authorization = {
        "host_authorization_policy_version": "host-authorization-policy.v1",
        "policy_id": "enterprise-local-test.v1",
        "identity_provider_reference": "identity-provider:enterprise.local-test.v1",
        "issuer": "https://identity.example.invalid/test",
        "audience": "aps-local-test",
        "environment": "TEST",
        "data_plane": "SIMULATION",
        "production_binding": False,
        "max_assertion_lifetime_seconds": 60,
        "revoked_subject_references": [],
        "revoked_assertion_references": [],
        "principals": [
            {
                "subject_ref": "subject:local-test",
                "actor_ref": "actor:local-test",
                "operations": ["getHeadlessPlanningRunStatus"],
                "scopes": [scope],
            }
        ],
    }
    (directory / "authorization.json").write_text(
        json.dumps(authorization), encoding="utf-8"
    )
    env = {
        "ENVIRONMENT": "test",
        "DATA_PLANE": "simulation",
        "RUNTIME_SOURCE_SHA": "39149091859b35b1303002a237a3cf1344572773",
        "RUNTIME_FINGERPRINT": "sha256:09559ca7f22af19c3f2b5fbb7f802c8d681574007fa31b2b8709ce5754b1083e",
        "KIT_VERSION": "1.0.0",
        "KIT_FINGERPRINT": "sha256:ee2a3a407337e595ca724ed2a92540e911c5fad7272e472f2d3ef3297a14a361",
        "PLANNING_POLICY_FILE": path("planning-policy.json"),
        "SOLVE_LIMITS_FILE": path("solve-limits.json"),
        "HTTP_POLICY_FILE": path("http-policy.json"),
        "AUTHORIZATION_POLICY_FILE": path("authorization.json"),
        "IDENTITY_PROVIDER": "LOCAL_TEST_TOKEN",
        "IDENTITY_ISSUER": authorization["issuer"],
        "IDENTITY_AUDIENCE": authorization["audience"],
        "IDENTITY_CLIENT_ID": "not-applicable-local-test",
        "IDENTITY_SUBJECT": "subject:local-test",
        "IDENTITY_TOKEN_FILE": path("identity-token"),
        "API_DOMAIN": "aps.example.invalid",
        "API_BIND": "127.0.0.1",
        "API_PORT": "8000",
        "TLS_CERT_FILE": path("tls.crt"),
        "TLS_KEY_FILE": path("tls.key"),
        "DATA_VOLUME": path("data"),
        "BACKUP_VOLUME": path("backup"),
        "CPU_LIMIT": "1.0",
        "MEMORY_MIB": "1024",
        "WORKER_CONCURRENCY": "1",
        "LOG_LEVEL": "INFO",
        "HEARTBEAT_SECONDS": "30",
        "LEASE_SECONDS": "120",
        "EXTENSION_MODE": "none",
    }
    for prefix, index in (("DB", None), ("REDIS", 0), ("BROKER", 1), ("RESULT", 2)):
        env.update(
            {
                prefix + "_HOST": "db.invalid" if prefix == "DB" else "redis.invalid",
                prefix + "_PORT": "5432" if prefix == "DB" else "6379",
                prefix + "_USER_FILE": path(
                    "db-user" if prefix == "DB" else "redis-user"
                ),
                prefix + "_PASSWORD_FILE": path("password"),
            }
        )
        env[prefix + ("_NAME" if prefix == "DB" else "_INDEX")] = (
            "synthetic_test" if index is None else str(index)
        )
    write_env(directory, env)
    return env


def write_env(directory: Path, env: dict[str, str]) -> Path:
    path = directory / "deployment.env"
    path.write_text(
        "".join(f"{k}={v}\n" for k, v in sorted(env.items())),
        encoding="utf-8",
        newline="\n",
    )
    return path


def add_extension(
    directory: Path, env: dict[str, str], *, container_paths: bool = False
) -> None:
    # Build-side fixture only. Deployment bootstrap never imports tooling or signs.
    from aps_extension_tooling.packaging import extension_wheel_for_source
    from aps_extension_sdk import fingerprint_json
    from app.extensions.loader import runtime_extension_signature
    import hashlib

    def path(name):
        return "/case/" + name if container_paths else str((directory / name).resolve())

    project = ROOT / "examples/enterprise-extensions/alpha-resource-tag"
    manifest = json.loads(
        (project / "extension/extension-manifest.json").read_text(encoding="utf-8")
    )
    config = json.loads(
        (project / "extension/extension-configuration.json").read_text(encoding="utf-8")
    )
    filename, raw = extension_wheel_for_source(
        distribution_name="example-alpha-aps-extension",
        package_name="example_alpha_extension",
        owner="PlantNexus Synthetic Reference Alpha",
        repository_url="https://example.invalid/plantnexus/alpha-aps-extension",
        license_expression="LicenseRef-PlantNexus-Synthetic-Reference",
        source_root=project / "src",
    )
    assert "sha256:" + hashlib.sha256(raw).hexdigest() == manifest["artifact"]["digest"]
    (directory / filename).write_bytes(raw)
    (directory / "extension-key").write_text(CANARY + "-extension", encoding="utf-8")
    (directory / "extension-manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    (directory / "extension-config.json").write_text(
        json.dumps(config), encoding="utf-8"
    )
    entry = {
        "extension_id": manifest["extension_id"],
        "extension_version": manifest["extension_version"],
        "manifest_path": "extension-manifest.json",
        "artifact_digest": manifest["artifact"]["digest"],
        "manifest_fingerprint": manifest["manifest_fingerprint"],
        "configuration_path": "extension-config.json",
        "configuration_fingerprint": config["configuration_fingerprint"],
        "allowed_capabilities": sorted(
            {v for c in manifest["contributions"] for v in c["capabilities"]}
        ),
        "signature_key_id": "enterprise.test.key.v1",
    }
    entry["signature"] = runtime_extension_signature(
        entry, verification_key=(CANARY + "-extension").encode()
    )
    catalog = {
        "catalog_version": "aps-runtime-extension-catalog.v1",
        "runtime_version": "0.1.0",
        "sdk_api_version": "1.0.0",
        "registry_protocol_version": "plugin-registry.v1",
        "compatibility": json.loads(
            (
                ROOT
                / "backend/aps_extension_sdk/contracts/samples/extension-compatibility.v1.synthetic.json"
            ).read_text(encoding="utf-8")
        ),
        "invocation_timeout_ms": 1000,
        "startup_timeout_ms": 30000,
        "extensions": [entry],
    }
    catalog["catalog_fingerprint"] = fingerprint_json(catalog)
    (directory / "extension-catalog.json").write_text(
        json.dumps(catalog), encoding="utf-8"
    )
    lock = {
        "lock_version": "enterprise-extension-lock.v1",
        "runtime_source_sha": env["RUNTIME_SOURCE_SHA"],
        "kit_version": env["KIT_VERSION"],
        "kit_fingerprint": env["KIT_FINGERPRINT"],
        "catalog_fingerprint": catalog["catalog_fingerprint"],
        "artifacts": [
            {
                "extension_id": entry["extension_id"],
                "extension_version": entry["extension_version"],
                "wheel_file": path(filename),
                "artifact_digest": entry["artifact_digest"],
            }
        ],
    }
    (directory / "extension-lock.json").write_text(json.dumps(lock), encoding="utf-8")
    env.update(
        {
            "EXTENSION_MODE": "local",
            "EXTENSION_LOCK_FILE": path("extension-lock.json"),
            "EXTENSION_CATALOG_FILE": path("extension-catalog.json"),
            "EXTENSION_KEY_FILE": path("extension-key"),
            "EXTENSION_KEY_ID": entry["signature_key_id"],
        }
    )
    write_env(directory, env)
