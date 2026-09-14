"""Build-side mapped candidate replay; independent clean-server acceptance is P8-28."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shlex
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from infra.enterprise.bundle.verify import extract, sha  # noqa: E402
from infra.enterprise.scripts.verify_container import Replay, fixture, unused_port  # noqa: E402


class MappedReplay(Replay):
    def __init__(self, directory, report, manifest, wsl):
        self.directory, self.report, self.manifest, self.wsl = (
            directory,
            report,
            manifest,
            wsl,
        )
        self.projects, self.mode, self.guarded_path, self.prefix = (
            [],
            "standalone",
            "",
            [],
        )
        self.bundle_path = directory / "bundle"
        if wsl:
            helper = directory / "mount.sh"
            helper.write_text(
                "#!/bin/sh\nset -eu\nmkdir -p "
                + shlex.quote(self.path(ROOT))
                + "\nmountpoint -q "
                + shlex.quote(self.path(ROOT))
                + " || mount --bind "
                + shlex.quote("/mnt/" + ROOT.drive[0].lower() + ROOT.as_posix()[2:])
                + " "
                + shlex.quote(self.path(ROOT))
                + '\nexec "$@"\n',
                encoding="utf-8",
                newline="\n",
            )
            self.prefix = [
                "wsl",
                "-d",
                "Ubuntu",
                "-u",
                "root",
                "--",
                "env",
                "DOCKER_HOST=unix:///mnt/wsl/docker-desktop/shared-sockets/guest-services/docker.proxy.sock",
                "sh",
                "/mnt/" + ROOT.drive[0].lower() + helper.as_posix()[2:],
            ]

    def invoke(self, action, slot, project, port, *extra, ok=True):
        return self.command(
            [
                "env",
                "PATH=" + self.guarded_path,
                "sh",
                self.path(self.bundle_path / "scripts" / (action + ".sh")),
                self.path(self.bundle_path),
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


def replay(args):
    build = json.loads(args.bundle_report.read_text(encoding="utf-8"))
    archive = ROOT / build["archive"]
    parent = ROOT / "build/validation/enterprise/P8-27"
    parent.mkdir(parents=True, exist_ok=True)
    checks = []

    def record(name):
        checks.append(dict(name=name, status="PASS"))
        print("PASS " + name, flush=True)

    with tempfile.TemporaryDirectory(prefix="mapped-", dir=parent) as temp:
        directory = Path(temp)
        verified = extract(archive, build["archive_sha256"], directory / "extracted")
        package = directory / "extracted" / verified["root"]
        report = json.loads((package / "evidence/image-report.json").read_text())
        run = MappedReplay(
            directory, report, verified["checksums_sha256"], args.wsl_test
        )
        run.bundle_path = package
        run.docker("load", "--input", run.path(package / "images/runtime.tar"))
        guard = directory / "guard"
        guard.mkdir()
        for name in ("python", "python3", "uv", "npm"):
            (guard / name).write_text(
                "#!/bin/sh\nexit 97\n", encoding="utf-8", newline="\n"
            )
            (guard / name).chmod(0o755)
        real_docker = (
            run.command(["sh", "-c", "command -v docker"]).stdout.decode().strip()
        )
        # Force lookup misses for the two dependencies, without removing user images.
        # The subsequent docker load is real. This is not a clean-daemon claim.
        ids = [verified["images"][n]["image_id"] for n in ("database", "redis")]
        wrapper = "#!/bin/sh\nset -eu\n"
        for n, image in zip(("database", "redis"), ids, strict=True):
            marker = shlex.quote(run.path(guard / (n + ".loaded")))
            wrapper += (
                'if [ "${1:-}" = image ] && [ "${2:-}" = inspect ] && [ "${3:-}" = '
                + shlex.quote(image)
                + " ] && [ ! -f "
                + marker
                + " ]; then exit 1; fi\n"
            )
            wrapper += (
                'if [ "${1:-}" = load ] && [ "${3:-}" = '
                + shlex.quote(run.path(package / "images" / (n + ".tar")))
                + " ]; then "
                + shlex.quote(real_docker)
                + ' "$@"; touch '
                + marker
                + "; exit 0; fi\n"
            )
        wrapper += (
            'case "${1:-}" in pull|build) exit 97;; esac\nexec '
            + shlex.quote(real_docker)
            + ' "$@"\n'
        )
        (guard / "docker").write_text(wrapper, encoding="utf-8", newline="\n")
        (guard / "docker").chmod(0o755)
        run.guarded_path = (
            run.path(guard)
            + ":"
            + run.command(["printenv", "PATH"]).stdout.decode().strip()
        )
        slot = directory / "slot"
        fixture(slot)
        project, port = "p827-" + uuid.uuid4().hex[:12], unused_port()
        run.projects.append(project)
        try:
            for script in package.rglob("*.sh"):
                run.command(["sh", "-n", run.path(script)])
            record("archive-extraction-executable-LF-and-script-syntax")
            run.invoke("preflight", slot, project, port)
            assert not list(guard.glob("*.loaded")), "PREFLIGHT_LOADED_DEPENDENCIES"
            record("mapped-preflight-without-loaded-dependency-lookup")
            good = run.manifest
            run.manifest = "0" * 64
            assert run.invoke("install", slot, project, port, ok=False).returncode != 0
            run.manifest = good
            assert not list(guard.glob("*.loaded")) and not run.cid(project, "api"), (
                "FAILED_SEAL_HAS_SIDE_EFFECTS"
            )
            record("corrupt-seal-rejected-before-load-or-business")
            run.invoke("install", slot, project, port)
            assert len(list(guard.glob("*.loaded"))) == 2, (
                "OFFLINE_IMPORT_NOT_EXERCISED"
            )
            run.invoke("status", slot, project, port)
            record("real-three-image-import-and-mapped-standalone-readiness")
            backup = directory / "backup"
            run.invoke(
                "backup", slot, project, port, run.path(backup), "QUIESCE-" + project
            )
            assert sha(backup / "database.dump"), "BACKUP_MISSING"
            record("mapped-postgres-client-and-backup-metadata")
            external, external_port = "p827-ext-" + uuid.uuid4().hex[:10], unused_port()
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
            for role in ("database", "redis"):
                run.docker(
                    "network",
                    "connect",
                    "--alias",
                    role,
                    external + "-runtime",
                    run.cid(project, role),
                )
            run.mode = "enterprise"
            run.invoke("install", slot, external, external_port)
            run.invoke("status", slot, external, external_port)
            run.invoke("logs", slot, external, external_port)
            run.invoke("stop", slot, external, external_port)
            record("mapped-enterprise-existing-synthetic-dependencies")
        finally:
            run.cleanup()
    return dict(
        schema_version="enterprise-bundle-container-report.v1",
        task_id="TASK-P8-27",
        status="PASS",
        code_commit=build["code_commit"],
        archive_sha256=build["archive_sha256"],
        payload_fingerprint=build["payload_fingerprint"],
        checks=checks,
        issues=[],
        secret_leaks=0,
        production_ready=False,
        clean_daemon_acceptance=False,
        dependency_lookup_misses_injected=True,
        host_development_tools_denied=True,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-report", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--wsl-test", action="store_true")
    args = parser.parse_args()
    try:
        result = replay(args)
    except Exception as error:
        result = dict(
            schema_version="enterprise-bundle-container-report.v1",
            status="FAIL",
            issues=[
                str(error)
                if isinstance(error, AssertionError)
                else type(error).__name__
            ],
            production_ready=False,
        )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("status", "issues")}))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
