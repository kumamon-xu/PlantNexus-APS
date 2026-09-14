"""Build-side fresh Shell operations replay. Never distributed as an operator prerequisite."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import shlex
import subprocess
import sys
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from infra.enterprise.compose.verify_container import fixture, unused_port  # noqa: E402


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def seal(directory):
    files = sorted(
        p for p in directory.rglob("*") if p.is_file() and p.name != "SHA256SUMS"
    )
    manifest = directory / "SHA256SUMS"
    manifest.write_text(
        "".join(
            sha(p) + "  " + p.relative_to(directory).as_posix() + "\n" for p in files
        ),
        encoding="utf-8",
        newline="\n",
    )
    return sha(manifest)


def bundle(directory, image_report):
    report = json.loads(image_report.read_text(encoding="utf-8"))
    archive = Path(report["image_archive"])
    if not archive.is_file():
        archive = image_report.parent / archive.name
    assert sha(archive) == report["image_archive_sha256"], "IMAGE_ARCHIVE_CHANGED"
    directory.mkdir()
    os.link(archive, directory / "image.tar")
    shutil.copyfile(image_report, directory / "image-report.json")
    for folder in ("bootstrap", "compose", "scripts"):
        shutil.copytree(
            ROOT / "infra/enterprise" / folder,
            directory / "infra/enterprise" / folder,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
    for path in directory.rglob("*.sh"):
        path.chmod(0o755)
    return report, seal(directory)


class Replay:
    def __init__(self, directory, report, manifest, wsl):
        self.directory, self.report, self.manifest, self.wsl = (
            directory,
            report,
            manifest,
            wsl,
        )
        self.prefix = (
            [
                "wsl",
                "-d",
                "Ubuntu",
                "-u",
                "root",
                "--",
                "env",
                "DOCKER_HOST=unix:///mnt/wsl/docker-desktop/shared-sockets/guest-services/docker.proxy.sock",
            ]
            if wsl
            else []
        )
        self.projects = []
        self.mode = "standalone"
        self.guarded_path = ""
        if wsl:
            mirrored = self.path(ROOT)
            source = "/mnt/" + ROOT.drive[0].lower() + ROOT.as_posix()[2:]
            helper = ROOT / "build/validation/enterprise/P8-26/wsl-mount.sh"
            helper.write_text(
                "#!/bin/sh\nset -eu\nmkdir -p "
                + shlex.quote(mirrored)
                + "\nmountpoint -q "
                + shlex.quote(mirrored)
                + " || mount --bind "
                + shlex.quote(source)
                + " "
                + shlex.quote(mirrored)
                + '\nexec "$@"\n',
                encoding="utf-8",
                newline="\n",
            )
            helper_source = "/mnt/" + ROOT.drive[0].lower() + helper.as_posix()[2:]
            self.prefix += ["sh", helper_source]

    def path(self, path):
        value = path.resolve().as_posix()
        return "/mnt/host/" + value[0].lower() + value[2:] if self.wsl else value

    def command(self, command, *, ok=True, timeout=360):
        from tests.enterprise.configuration_fixtures import CANARY

        result = subprocess.run(
            self.prefix + command, capture_output=True, timeout=timeout, check=False
        )
        assert CANARY.encode() not in result.stdout + result.stderr, (
            "OPERATIONS_SECRET_LEAK"
        )
        if ok:
            codes = re.findall(
                r'"code":\s*"([A-Z_]{1,64})"',
                (result.stdout + result.stderr).decode(errors="replace"),
            )
            assert result.returncode == 0, (
                "SHELL_COMMAND_FAILED_"
                + command[0].split("/")[-1]
                + "_"
                + "_".join(codes)
            )
        return result

    def invoke(self, action, slot, project, port, *extra, ok=True):
        return self.command(
            [
                "env",
                "PATH=" + self.guarded_path,
                "sh",
                self.path(
                    self.directory
                    / "bundle/infra/enterprise/scripts"
                    / (action + ".sh")
                ),
                self.path(self.directory / "bundle"),
                self.manifest,
                self.report["image_id"],
                self.path(slot),
                project,
                str(port),
                self.mode,
                *extra,
            ],
            ok=ok,
        )

    def docker(self, *args, ok=True):
        return self.command(["docker", *args], ok=ok)

    def cid(self, project, role):
        return (
            self.docker(
                "ps",
                "-aq",
                "--filter",
                "label=com.docker.compose.project=" + project,
                "--filter",
                "label=com.docker.compose.service=" + role,
            )
            .stdout.decode()
            .strip()
        )

    def python(self, project, code):
        return self.docker("exec", self.cid(project, "api"), "python", "-c", code)

    def cleanup(self):
        # Only random, recorded fixture projects; never generic docker prune.
        for project in self.projects:
            ids = (
                self.docker(
                    "ps",
                    "-aq",
                    "--filter",
                    "label=com.docker.compose.project=" + project,
                )
                .stdout.decode()
                .split()
            )
            if ids:
                self.docker("rm", "-f", *ids)
            volumes = (
                self.docker(
                    "volume",
                    "ls",
                    "-q",
                    "--filter",
                    "label=com.docker.compose.project=" + project,
                )
                .stdout.decode()
                .split()
            )
            if volumes:
                self.docker("volume", "rm", *volumes)
            self.docker("network", "rm", project + "-runtime", ok=False)


def verify(args):
    from tests.enterprise.configuration_fixtures import (
        add_extension,
        write_env,
        container_readable_fixture,
    )

    parent = ROOT / "build/validation/enterprise/P8-26"
    parent.mkdir(parents=True, exist_ok=True)
    checks = []

    def record(name):
        checks.append({"name": name, "status": "PASS"})
        print("PASS " + name, flush=True)

    with tempfile.TemporaryDirectory(prefix="synthetic-", dir=parent) as temp:
        directory = Path(temp)
        report, manifest = bundle(directory / "bundle", args.image_report)
        payloads = [
            {"path": line.split()[1], "sha256": line.split()[0]}
            for line in (directory / "bundle/SHA256SUMS").read_text().splitlines()
            if line.split()[1].startswith("infra/enterprise/scripts/")
        ]
        run = Replay(directory, report, manifest, args.wsl_test)
        guard = directory / "deny-host-development-tools"
        guard.mkdir()
        for name in ("python", "python3", "uv", "npm"):
            stub = guard / name
            stub.write_text(
                '#!/bin/sh\nprintf "HOST_DEVELOPMENT_TOOL_FORBIDDEN\\n" >&2\nexit 97\n',
                encoding="utf-8",
                newline="\n",
            )
            stub.chmod(0o755)
        run.guarded_path = (
            run.path(guard)
            + ":"
            + run.command(["printenv", "PATH"]).stdout.decode().strip()
        )
        slot = directory / "slot"
        config, secrets, values = fixture(slot)
        add_extension(config, values, container_paths=True)
        for key in values:
            values[key] = values[key].replace("/case/", "/etc/plantnexus/")
        (secrets / "extension_key").write_bytes((config / "extension-key").read_bytes())
        (config / "extension-key").unlink()
        values["EXTENSION_KEY_FILE"] = "/run/secrets/extension_key"
        lock = config / "extension-lock.json"
        lock.write_text(
            lock.read_text(encoding="utf-8").replace("/case/", "/etc/plantnexus/"),
            encoding="utf-8",
        )
        write_env(config, values)
        container_readable_fixture(secrets)
        project = "p826-" + uuid.uuid4().hex[:12]
        port = unused_port()
        run.projects.append(project)
        try:
            for script in (directory / "bundle/infra/enterprise/scripts").glob("*.sh"):
                run.command(["sh", "-n", run.path(script)])
            run.invoke("preflight", slot, project, port)
            record("shell-syntax-and-offline-preflight")
            good = run.manifest
            run.manifest = "0" * 64
            assert run.invoke("install", slot, project, port, ok=False).returncode != 0
            run.manifest = good
            assert not run.cid(project, "api")
            record("wrong-package-blocks-before-business")
            original = (config / "deployment.env").read_bytes()
            (config / "deployment.env").write_bytes(
                original.replace(b"CPU_LIMIT=", b"MISSING_CPU_LIMIT=")
            )
            assert run.invoke("install", slot, project, port, ok=False).returncode != 0
            (config / "deployment.env").write_bytes(original)
            record("missing-configuration-refused")
            run.invoke("install", slot, project, port)
            record("empty-database-exact-head-and-extension-start")
            run.invoke("install", slot, project, port)
            record("repeated-install-and-migration")
            run.python(
                project,
                "from bootstrap.services import prepare,CONFIG,database;from sqlalchemy import text;from redis import Redis;p=prepare(CONFIG);e=database(p);c=e.connect();c.execute(text('CREATE TABLE p826_marker (value INTEGER PRIMARY KEY)'));c.execute(text('INSERT INTO p826_marker VALUES (26)'));c.commit();c.close();e.dispose();r=Redis.from_url(p.settings.redis_url.get_secret_value());r.set('p826:persistence','26');r.close()",
            )
            run.invoke("stop", slot, project, port)
            run.invoke("stop", slot, project, port)
            run.invoke("start", slot, project, port)
            run.python(
                project,
                "from bootstrap.services import prepare,CONFIG,database;from sqlalchemy import text;from redis import Redis;p=prepare(CONFIG);e=database(p);c=e.connect();assert c.execute(text('SELECT value FROM p826_marker')).scalar()==26;c.close();e.dispose();r=Redis.from_url(p.settings.redis_url.get_secret_value());assert r.get('p826:persistence')==b'26';r.close()",
            )
            record("repeat-stop-and-restart-retain-postgres-redis")
            old_worker = run.cid(project, "worker")
            run.docker("stop", run.cid(project, "redis"), run.cid(project, "api"))
            assert run.invoke("status", slot, project, port, ok=False).returncode != 0
            run.invoke("start", slot, project, port)
            assert run.cid(project, "worker") != old_worker
            run.invoke("status", slot, project, port)
            run.invoke("logs", slot, project, port)
            record("dependency-recovery-recreates-named-worker")
            backup = directory / "backup"
            assert (
                run.invoke(
                    "backup", slot, project, port, run.path(backup), "wrong", ok=False
                ).returncode
                != 0
            )
            run.invoke(
                "backup", slot, project, port, run.path(backup), "QUIESCE-" + project
            )
            backup_sha = sha(backup / "SHA256SUMS")
            metadata = json.loads((backup / "metadata.json").read_text())
            assert (
                len(
                    metadata["identity"]["descriptor"]["extension_adapter"][
                        "extensions"
                    ]
                )
                > 0
            )
            assert metadata["migration_head"] == "0009_host_authorization_audit"
            record("quiesced-backup-binds-runtime-kit-extension")
            assert (
                run.invoke(
                    "restore",
                    slot,
                    project,
                    port,
                    run.path(backup),
                    backup_sha,
                    "TARGET-" + project,
                    ok=False,
                ).returncode
                != 0
            )
            record("source-target-restore-refused")
            # Enterprise mode consumes explicitly connected synthetic dependencies.
            external = "p826-external-" + uuid.uuid4().hex[:10]
            run.projects.append(external)
            run.docker(
                "network",
                "create",
                "--label",
                "com.docker.compose.project=" + external,
                "--label",
                "com.docker.compose.network=runtime",
                external + "-runtime",
            )
            for role, alias in (("database", "database"), ("redis", "redis")):
                run.docker(
                    "network",
                    "connect",
                    "--alias",
                    alias,
                    external + "-runtime",
                    run.cid(project, role),
                )
            run.mode = "enterprise"
            external_port = unused_port()
            run.invoke("install", slot, external, external_port)
            run.invoke("status", slot, external, external_port)
            run.invoke(
                "backup",
                slot,
                external,
                external_port,
                run.path(directory / "external-backup"),
                "QUIESCE-" + external,
            )
            run.invoke("stop", slot, external, external_port)
            record("enterprise-shell-install-status-and-client-backup")
            run.mode = "standalone"
            for action in ("restore", "rollback"):
                target = "p826-" + action + "-" + uuid.uuid4().hex[:10]
                run.projects.append(target)
                restore_slot = directory / action
                shutil.copytree(slot, restore_slot)
                target_port = unused_port()
                assert (
                    run.invoke(
                        action,
                        restore_slot,
                        target,
                        target_port,
                        run.path(backup),
                        "0" * 64,
                        "TARGET-" + target,
                        ok=False,
                    ).returncode
                    != 0
                )
                assert (
                    run.invoke(
                        action,
                        restore_slot,
                        target,
                        target_port,
                        run.path(backup),
                        backup_sha,
                        "wrong",
                        ok=False,
                    ).returncode
                    != 0
                )
                run.invoke(
                    action,
                    restore_slot,
                    target,
                    target_port,
                    run.path(backup),
                    backup_sha,
                    "TARGET-" + target,
                )
                run.python(
                    target,
                    "from bootstrap.services import prepare,CONFIG,database;from sqlalchemy import text;e=database(prepare(CONFIG));c=e.connect();assert c.execute(text('SELECT value FROM p826_marker')).scalar()==26;c.close();e.dispose()",
                )
                run.invoke("stop", restore_slot, target, target_port)
                assert (
                    run.invoke(
                        action,
                        restore_slot,
                        target,
                        target_port,
                        run.path(backup),
                        backup_sha,
                        "TARGET-" + target,
                        ok=False,
                    ).returncode
                    != 0
                )
                run.invoke("start", restore_slot, target, target_port)
                record(
                    action + "-isolated-identity-parity-and-existing-data-protection"
                )
        finally:
            run.cleanup()
    return dict(
        schema_version="enterprise-operations-report.v1",
        task_id="TASK-P8-26",
        status="PASS",
        code_commit=subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip(),
        image_id=report["image_id"],
        image_archive_sha256=report["image_archive_sha256"],
        checks=checks,
        issues=[],
        secret_leaks=0,
        production_ready=False,
        host_python_required=False,
        deployment_payload_manifest_sha256=manifest,
        shell_payloads=payloads,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image-report", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument(
        "--wsl-test",
        action="store_true",
        help="Explicit local test via preconfigured Ubuntu/root Docker socket and mirrored bind path",
    )
    args = parser.parse_args()
    start = time.monotonic()
    result: dict
    try:
        result = verify(args)
    except Exception as error:
        detail = (
            str(error)
            if isinstance(error, AssertionError)
            and re.fullmatch(r"[A-Za-z0-9_-]{1,512}", str(error))
            else type(error).__name__
        )
        print(detail, flush=True)
        result = dict(
            schema_version="enterprise-operations-report.v1",
            task_id="TASK-P8-26",
            status="FAIL",
            issues=[detail],
            production_ready=False,
        )
    result["elapsed_seconds"] = round(time.monotonic() - start, 2)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("status", "issues", "elapsed_seconds")}))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
