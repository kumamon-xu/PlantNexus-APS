"""Build-side synthetic verification; never mount this driver as a business entrypoint."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


def execute(command, **kwargs):
    return subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=180,
        check=False,
        **kwargs,
    )


def scan_layers(path, needle):
    with tarfile.open(path) as archive:
        for member in archive:
            if not member.isfile():
                continue
            stream = archive.extractfile(member)
            assert stream is not None
            magic = stream.read(2)
            stream.seek(0)
            content = gzip.GzipFile(fileobj=stream) if magic == b"\x1f\x8b" else stream
            tail = b""
            while block := content.read(1024 * 1024):
                assert needle not in tail + block, "IMAGE_CANARY_LEAK"
                tail = block[-len(needle) :]


def verify(args):
    from tests.enterprise.configuration_fixtures import (
        CANARY,
        add_extension,
        create_fixture,
        write_env,
    )

    image = json.loads(args.image_report.read_text(encoding="utf-8"))
    assert image["status"] == "PASS" and not image["issues"]
    identity = json.loads(
        subprocess.check_output(["docker", "image", "inspect", image["image_id"]])
    )[0]
    assert (
        identity["Id"] == image["image_id"]
        and identity["Config"]["User"] == "10001:10001"
    )
    image_archive = args.image_archive or ROOT / image["image_archive"]
    with image_archive.open("rb") as stream:
        assert (
            hashlib.file_digest(stream, "sha256").hexdigest()
            == image["image_archive_sha256"]
        )
    scan_layers(image_archive, CANARY.encode())
    payloads = []
    for folder in ("bootstrap", "config"):
        for path in sorted((ROOT / "infra/enterprise" / folder).rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                raw = path.read_bytes()
                assert CANARY.encode() not in raw, "TEMPLATE_CANARY_LEAK"
                payloads.append(
                    {
                        "path": path.relative_to(ROOT).as_posix(),
                        "sha256": hashlib.sha256(raw).hexdigest(),
                    }
                )
    records = []
    with tempfile.TemporaryDirectory(prefix="p8-24-synthetic-") as temp:
        root = Path(temp)
        env = create_fixture(root, container_paths=True)
        original = dict(env)
        # All stdout/stderr is inspected but only stable outcomes are retained.
        driver = """
import json, os
import app.infrastructure.database as db
calls=[]
def forbidden(*a, **kw):
    calls.append('database')
    raise AssertionError('database client before preflight')
db.create_database_client=forbidden
from bootstrap.run import main
if os.environ.get('TEST_SYMLINK')=='1':
    os.symlink('/case/password','/tmp/password-link')
options=['--role','validator'] if os.environ.get('TEST_VALIDATOR')=='1' else ['--check']
result=main(['--config','/case/deployment.env',*options])
assert not calls
raise SystemExit(result)
"""
        for name in (
            "valid-empty",
            "valid-validator",
            "missing",
            "placeholder",
            "secret-writable",
            "secret-symlink",
            "wrong-kit",
            "valid-extension",
            "wrong-extension-key",
        ):
            env = dict(original)
            if name == "missing":
                del env["DB_HOST"]
            if name == "placeholder":
                env["DB_HOST"] = "__REQUIRED__"
            if name == "wrong-kit":
                env["KIT_VERSION"] = "9.0.0"
            if name == "secret-symlink":
                env["DB_PASSWORD_FILE"] = "/tmp/password-link"
            if name in ("valid-extension", "wrong-extension-key"):
                add_extension(root, env, container_paths=True)
                if name == "wrong-extension-key":
                    (root / "extension-key").write_text(
                        "wrong-key-" * 8, encoding="utf-8"
                    )
            write_env(root, env)
            command = [
                "docker",
                "run",
                "--rm",
                "--network=none",
                "--read-only",
                "--tmpfs",
                "/tmp",
                "--cap-drop=ALL",
                "--security-opt=no-new-privileges",
                "-v",
                f"{ROOT / 'infra/enterprise/bootstrap'}:/opt/enterprise/bootstrap:ro",
                "-v",
                f"{root}:/case:ro",
                "-w",
                "/opt/enterprise",
            ]
            if name == "secret-writable":
                command.extend(["-v", f"{root / 'password'}:/case/password:rw"])
            if name == "secret-symlink":
                command.extend(["-e", "TEST_SYMLINK=1"])
            if name == "valid-validator":
                command.extend(["-e", "TEST_VALIDATOR=1"])
            result = execute([*command, image["image_id"], "python", "-c", driver])
            assert CANARY.encode() not in result.stdout + result.stderr, (
                "PROCESS_CANARY_LEAK"
            )
            expected = 0 if name.startswith("valid-") else 1
            try:
                value = json.loads(result.stdout)
            except ValueError:
                raise AssertionError(f"CONTAINER_RESULT_INVALID:{name}") from None
            if result.returncode != expected:
                code = str(value.get("code", "UNREPORTED"))
                field = str(value.get("field", "UNREPORTED"))
                if not re.fullmatch("[A-Z_]+", code) or not re.fullmatch(
                    "[A-Za-z_]+", field
                ):
                    code, field = "UNREPORTED", "UNREPORTED"
                raise AssertionError(
                    f"CONTAINER_CASE_FAILED:{name}:{result.returncode}:{code}:{field}"
                )
            assert value["status"] == ("PASS" if expected == 0 else "FAIL")
            records.append(
                {
                    "case": name,
                    "status": "PASS",
                    "expected_exit": expected,
                    "observed_code": value.get("code"),
                    "database_clients_created": 0,
                }
            )
        write_env(root, original)
        process_env = dict(os.environ, RUNTIME_IMAGE=image["tag"])
        rendered = execute(
            [
                "docker",
                "compose",
                "--env-file",
                str(root / "deployment.env"),
                "-f",
                str(ROOT / "infra/enterprise/config/secrets.example.yml"),
                "config",
                "--format",
                "json",
            ],
            env=process_env,
        )
        assert rendered.returncode == 0, "COMPOSE_RENDER_FAILED"
        assert CANARY.encode() not in rendered.stdout + rendered.stderr, (
            "COMPOSE_CANARY_LEAK"
        )
        compose = json.loads(rendered.stdout)
        service = compose["services"]["runtime"]
        assert service["read_only"] and not service.get("environment")
        assert all(v.get("read_only") for v in service["volumes"])
    commit = (
        subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
    )
    return {
        "schema_version": "enterprise-bootstrap-container-report.v1",
        "task_id": "TASK-P8-24",
        "code_commit": commit,
        "status": "PASS",
        "issues": [],
        "image_id": image["image_id"],
        "image_archive_sha256": image["image_archive_sha256"],
        "bootstrap_payloads": payloads,
        "checks": records,
        "compose_secret_interpolation": False,
        "canary_leak_count": 0,
        "read_only_mounts_verified": True,
        "original_runtime_loader_used": True,
        "package_scope": "bootstrap/config templates only; final offline package belongs to later tasks",
        "production_ready": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image-report", type=Path, required=True)
    parser.add_argument("--image-archive", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = verify(args)
    except Exception as error:
        report = {
            "status": "FAIL",
            "task_id": "TASK-P8-24",
            "issues": [
                str(error)
                if isinstance(error, AssertionError)
                else type(error).__name__
            ],
        }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "issues": report["issues"]}))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
