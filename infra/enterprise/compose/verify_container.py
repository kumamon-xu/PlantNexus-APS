"""Build-side isolated dual-mode replay; synthetic inputs never enter evidence."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from infra.enterprise.compose import control  # noqa: E402


def fixture(directory):
    from tests.enterprise.configuration_fixtures import (
        create_fixture,
        write_env,
        container_readable_fixture,
    )
    from app.planning.validation.problem_validator_check import formal_validation_vector

    config, secrets = directory / "config", directory / "secrets"
    secrets.mkdir(parents=True)
    values = create_fixture(config, container_paths=True)
    for name in list(values):
        values[name] = values[name].replace("/case/", "/etc/plantnexus/")
    mapping = {
        "DB_USER_FILE": "db-user",
        "DB_PASSWORD_FILE": "password",
        "IDENTITY_TOKEN_FILE": "identity-token",
        "TLS_KEY_FILE": "tls.key",
    }
    for prefix in ("REDIS", "BROKER", "RESULT"):
        mapping[prefix + "_USER_FILE"] = "redis-user"
        mapping[prefix + "_PASSWORD_FILE"] = "password"
    for field, source in mapping.items():
        name = field.removesuffix("_FILE").lower()
        (secrets / name).write_bytes((config / source).read_bytes())
        values[field] = "/run/secrets/" + name
    for source in set(mapping.values()):
        (config / source).unlink()
    values.update(
        API_BIND="0.0.0.0",
        DATA_VOLUME="/var/lib/plantnexus",
        BACKUP_VOLUME="/var/backups/plantnexus",
        DB_HOST="database",
        REDIS_HOST="redis",
        BROKER_HOST="redis",
        RESULT_HOST="redis",
        LOG_LEVEL="WARNING",
        HEARTBEAT_SECONDS="5",
        LEASE_SECONDS="20",
    )
    write_env(config, values)
    validation = config / "validation"
    validation.mkdir()
    for name, value in zip(
        ("problem", "candidate"), formal_validation_vector(), strict=True
    ):
        (validation / (name + ".json")).write_text(json.dumps(value), encoding="utf-8")
    for folder in (directory, config, validation, secrets):
        container_readable_fixture(folder)
    return config, secrets, values


class Target:
    def __init__(self, directory, document, project):
        self.project = project
        self.path = directory / (project + ".json")
        self.path.write_text(json.dumps(document), encoding="utf-8")
        self.command = ["docker", "compose", "-p", project, "-f", str(self.path)]
        self.last_codes = []

    def run(self, *args, ok=True, timeout=240):
        from tests.enterprise.configuration_fixtures import CANARY

        result = control.execute(self.command + list(args), timeout=timeout)
        # Secret logs are a test failure; raw output is never persisted.
        assert CANARY.encode() not in result.stdout + result.stderr, (
            "COMPOSE_SECRET_LEAK"
        )
        if ok and result.returncode:
            self.diagnostics()
            raise AssertionError(
                "COMPOSE_COMMAND_FAILED:"
                + "_".join(args[:2])
                + ":"
                + ",".join(self.last_codes)
            )
        return result

    def diagnostics(self):
        result = control.execute(self.command + ["logs", "--no-color"])
        self.last_codes = sorted(
            set(
                re.findall(
                    r'"code": "([A-Z_]+)"', result.stdout.decode(errors="replace")
                )
            )
        )

    def exec_python(self, role, code):
        return self.run("exec", "-T", role, "python", "-c", code).stdout

    def down(self, *, volumes=False):
        return self.run(
            "down", "--remove-orphans", *(["--volumes"] if volumes else []), timeout=90
        )


def unused_port():
    with socket.socket() as value:
        value.bind(("127.0.0.1", 0))
        return value.getsockname()[1]


def verify(args):
    report = json.loads(args.image_report.read_text(encoding="utf-8"))
    image_id = control.image_identity(report, report["tag"])
    locked = json.loads(
        (control.HERE / "dependencies.v1.json").read_text(encoding="utf-8")
    )
    # Acquisition is explicit build-side only; deployment control/Compose never pulls.
    if args.acquire_test_dependencies:
        for reference in locked["images"].values():
            result = control.execute(
                ["docker", "pull", "--platform", "linux/amd64", reference], timeout=180
            )
            assert result.returncode == 0, "TEST_DEPENDENCY_ACQUISITION_FAILED"
    checks = []

    def record(name, **details):
        checks.append({"name": name, "status": "PASS", **details})
        print("PASS " + name, flush=True)

    # Wrong approved tag mapping must fail before any Compose mutation.
    forged = deepcopy(report)
    forged["image_id"] = "sha256:" + "0" * 64
    try:
        control.image_identity(forged, report["tag"])
        raise AssertionError("WRONG_IMAGE_ACCEPTED")
    except control.DeploymentError as error:
        assert str(error) == "IMAGE_ID_MISMATCH"
    record("wrong-image-refused-before-compose")
    with tempfile.TemporaryDirectory(prefix="p8-25-synthetic-") as temp:
        directory = Path(temp)
        config, secrets, values = fixture(directory)
        for mode in ("standalone", "enterprise"):
            if mode == "enterprise":
                from tests.enterprise.configuration_fixtures import (
                    add_extension,
                    write_env,
                    container_readable_fixture,
                )

                add_extension(config, values, container_paths=True)
                for key in list(values):
                    values[key] = values[key].replace("/case/", "/etc/plantnexus/")
                (secrets / "extension_key").write_bytes(
                    (config / "extension-key").read_bytes()
                )
                (config / "extension-key").unlink()
                values["EXTENSION_KEY_FILE"] = "/run/secrets/extension_key"
                lock_path = config / "extension-lock.json"
                lock_path.write_text(
                    lock_path.read_text(encoding="utf-8").replace(
                        "/case/", "/etc/plantnexus/"
                    ),
                    encoding="utf-8",
                )
                write_env(config, values)
                container_readable_fixture(secrets)
            project = "p825-" + mode + "-" + uuid.uuid4().hex[:10]
            document = control.render(
                report=report,
                reference=report["tag"],
                mode=mode,
                config_dir=config.resolve(),
                secrets_dir=secrets.resolve(),
                project=project,
                port=unused_port(),
            )
            # Enterprise-shaped external fixtures remain on a no-egress test network.
            document["networks"]["runtime"]["internal"] = True
            target = Target(directory, document, project)
            dependency_target = target
            if mode == "enterprise":
                fixture_document = control.render(
                    report=report,
                    reference=report["tag"],
                    mode="standalone",
                    config_dir=config.resolve(),
                    secrets_dir=secrets.resolve(),
                    project=project,
                    port=unused_port(),
                )
                fixture_document["services"] = {
                    k: v
                    for k, v in fixture_document["services"].items()
                    if k in {"database", "redis"}
                }
                depdir = directory / "external"
                depdir.mkdir(exist_ok=True)
                dependency_target = Target(depdir, fixture_document, project)
            try:
                record(
                    mode + "-config",
                    services=sorted(document["services"]),
                    pull_policy="never",
                    isolated_network=True,
                )
                # Existing external dependencies are absent: migration must fail, no API/Worker.
                if mode == "enterprise":
                    refused = target.run("up", "-d", "api", "worker", ok=False)
                    assert refused.returncode != 0, "UNREADY_ACCEPTED"
                    running = (
                        target.run("ps", "--status", "running", "--services")
                        .stdout.decode()
                        .split()
                    )
                    assert not {"api", "worker"}.intersection(running), (
                        "UNREADY_BUSINESS_STARTED"
                    )
                    record("external-unready-refused")
                    target.run("rm", "-f", "migrate", "api", "worker")
                assert dependency_target is not None
                dependency_target.run(
                    "up", "-d", "--wait", "--wait-timeout", "90", "database", "redis"
                )
                target.run(
                    "run",
                    "--rm",
                    "--no-deps",
                    "migrate",
                    "python",
                    "-m",
                    "bootstrap.services",
                    "preflight",
                )
                target.run(
                    "up", "-d", "--wait", "--wait-timeout", "150", "api", "worker"
                )
                descriptors = [
                    json.loads(
                        target.exec_python(
                            role,
                            "from pathlib import Path;print(Path('/tmp/runtime-descriptor.json').read_text())",
                        )
                    )["descriptor"]
                    for role in ("api", "worker")
                ]
                assert descriptors[0] == descriptors[1], "API_WORKER_IDENTITY_MISMATCH"
                for role in ("migrate", "api", "worker"):
                    cid = target.run("ps", "-a", "-q", role).stdout.decode().strip()
                    observed = json.loads(
                        control.execute(["docker", "inspect", cid]).stdout
                    )[0]
                    assert observed["Image"] == image_id, "PROCESS_IMAGE_MISMATCH"
                validator_name = project + "-formal-validator"
                target.run("run", "--name", validator_name, "--no-deps", "validator")
                observed_validator = json.loads(
                    control.execute(["docker", "inspect", validator_name]).stdout
                )[0]
                assert (
                    observed_validator["Image"] == image_id
                    and observed_validator["HostConfig"]["NetworkMode"] == "none"
                ), "VALIDATOR_IMAGE_NETWORK_MISMATCH"
                assert control.execute(["docker", "rm", validator_name]).returncode == 0
                target.run("logs", "--no-color")
                record(
                    mode + "-four-roles",
                    image_id=image_id,
                    composition_fingerprint=descriptors[0]["composition_fingerprint"],
                    migration_head="0009_host_authorization_audit",
                    tls_ready=True,
                    named_worker_ready=True,
                    validator="PASS",
                    extension_count=len(
                        descriptors[0]["extension_adapter"]["extensions"]
                    ),
                )
                # Negative formal input is rejected by the same offline validator.
                candidate_path = config / "validation/candidate.json"
                candidate = candidate_path.read_bytes()
                invalid = json.loads(candidate)
                invalid["assignments"] = []
                candidate_path.write_text(json.dumps(invalid), encoding="utf-8")
                refused = target.run("run", "--rm", "--no-deps", "validator", ok=False)
                assert refused.returncode != 0, "INVALID_CANDIDATE_ACCEPTED"
                candidate_path.write_bytes(candidate)
                record(mode + "-validator-negative")
                if mode == "standalone":
                    # Persist a synthetic marker in both independent named volumes.
                    marker_code = "from bootstrap.services import prepare,CONFIG,database; from sqlalchemy import text; from redis import Redis; p=prepare(CONFIG); e=database(p); c=e.connect(); c.execute(text('CREATE TABLE enterprise_persistence_probe (value INTEGER PRIMARY KEY)')); c.execute(text('INSERT INTO enterprise_persistence_probe VALUES (25)')); c.commit(); c.close(); e.dispose(); r=Redis.from_url(p.settings.redis_url.get_secret_value());r.set('p825:persistence','25');r.close()"
                    target.exec_python("api", marker_code)
                    target.down()
                    target.run(
                        "up", "-d", "--wait", "--wait-timeout", "150", "api", "worker"
                    )
                    target.exec_python(
                        "api",
                        "from bootstrap.services import prepare,CONFIG,database; from sqlalchemy import text; from redis import Redis; p=prepare(CONFIG);e=database(p);c=e.connect();assert c.execute(text('SELECT value FROM enterprise_persistence_probe')).scalar()==25;c.close();e.dispose();r=Redis.from_url(p.settings.redis_url.get_secret_value());assert r.get('p825:persistence')==b'25';r.close()",
                    )
                    record("standalone-recreate-persists-postgres-and-redis")
                    # Corrupt only the throwaway fixture revision; frozen migration bytes untouched.
                    target.exec_python(
                        "api",
                        "from bootstrap.services import prepare,CONFIG,database;from sqlalchemy import text;e=database(prepare(CONFIG));c=e.connect();c.execute(text(\"UPDATE alembic_version SET version_num='unknown_p825_fixture'\"));c.commit();c.close();e.dispose()",
                    )
                    target.run("stop", "api", "worker")
                    target.run("rm", "-f", "api", "worker", "migrate")
                    refused = target.run("up", "-d", "api", "worker", ok=False)
                    assert refused.returncode != 0, "BAD_MIGRATION_ACCEPTED"
                    running = (
                        target.run("ps", "--status", "running", "--services")
                        .stdout.decode()
                        .split()
                    )
                    assert not {"api", "worker"}.intersection(running), (
                        "MIGRATION_FAILURE_BUSINESS_STARTED"
                    )
                    record("migration-failure-blocks-api-and-worker")
            finally:
                target.down(volumes=True)
                if dependency_target is not target and dependency_target is not None:
                    dependency_target.down(volumes=True)
    payloads = []
    for folder in ("bootstrap", "compose"):
        for path in sorted((ROOT / "infra/enterprise" / folder).glob("*")):
            if path.is_file():
                payloads.append(
                    {
                        "path": path.relative_to(ROOT).as_posix(),
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    }
                )
    return {
        "schema_version": "enterprise-compose-report.v1",
        "task_id": "TASK-P8-25",
        "status": "PASS",
        "code_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip(),
        "image_id": image_id,
        "image_archive_sha256": report["image_archive_sha256"],
        "dependencies": locked,
        "checks": checks,
        "payloads": payloads,
        "issues": [],
        "secret_leaks": 0,
        "production_ready": False,
        "external_dependencies": "isolated synthetic PostgreSQL/Redis fixtures, not real enterprise endpoints",
        "offline_scope": "preloaded exact images; internal Docker networks; no pull during deploy",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image-report", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--acquire-test-dependencies", action="store_true")
    args = parser.parse_args()
    started = time.monotonic()
    try:
        result = verify(args)
    except Exception as error:
        # Only stable assertion/error codes, never raw subprocess output or Secret.
        message = (
            str(error)
            if isinstance(error, (AssertionError, control.DeploymentError))
            and re.fullmatch(r"[A-Za-z0-9_ ,:-]{1,512}", str(error))
            else type(error).__name__
        )
        result = {
            "schema_version": "enterprise-compose-report.v1",
            "task_id": "TASK-P8-25",
            "status": "FAIL",
            "issues": [message],
            "production_ready": False,
        }
    result["elapsed_seconds"] = round(time.monotonic() - started, 2)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("status", "issues", "elapsed_seconds")}))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
