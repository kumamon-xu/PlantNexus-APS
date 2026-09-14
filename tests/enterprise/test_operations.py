from __future__ import annotations

from copy import deepcopy
import io
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest
import yaml

from infra.enterprise.scripts import metadata

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / "infra/enterprise/scripts"
IMAGE = "sha256:" + "1" * 64


@pytest.fixture
def backup(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "infra/enterprise"))
    config = tmp_path / "configuration"
    config.mkdir()
    (config / "policy.json").write_text('{"synthetic":true}', encoding="utf-8")
    monkeypatch.setattr(metadata, "CONFIG_DIRECTORY", config)
    identity = {
        "configuration": "sha256:" + "2" * 64,
        "descriptor": {
            "runtime_resolution": {
                "runtime_artifact_fingerprint": "runtime",
                "developer_kit_fingerprint": "kit",
            },
            "extension_adapter": {"extensions": ["alpha"]},
        },
    }
    for name in ("api", "worker"):
        (tmp_path / (name + ".json")).write_text(json.dumps(identity), encoding="utf-8")
    (tmp_path / "database.dump").write_bytes(b"synthetic database dump")
    doc = metadata.backup_metadata(tmp_path, IMAGE, "source-project")
    (tmp_path / "metadata.json").write_text(json.dumps(doc), encoding="utf-8")
    return tmp_path, doc


def test_backup_round_trip_binds_all_identity(backup):
    directory, doc = backup
    assert metadata.verify_backup(directory, IMAGE, "restore-project") == doc
    assert doc["quiescence"] == "API_AND_WORKER_STOPPED"
    assert doc["identity"]["descriptor"]["extension_adapter"]["extensions"] == ["alpha"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema_version", "other"),
        ("status", "FAIL"),
        ("image_id", "sha256:" + "0" * 64),
        ("migration_head", "unknown"),
        ("database_sha256", "0" * 64),
        ("identity", {}),
        ("source_project", "restore-project"),
        ("quiescence", "RUNNING"),
        ("production_ready", True),
    ],
)
def test_changed_backup_refused(backup, field, value):
    directory, doc = backup
    doc[field] = value
    (directory / "metadata.json").write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ValueError):
        metadata.verify_backup(directory, IMAGE, "restore-project")


@pytest.mark.parametrize(
    "name", ["database.dump", "metadata.json", "api.json", "worker.json"]
)
def test_missing_backup_component_cannot_default_to_success(backup, name):
    directory, _ = backup
    (directory / name).unlink()
    with pytest.raises(FileNotFoundError):
        metadata.verify_backup(directory, IMAGE, "restore-project")


def test_dump_corruption_detected(backup):
    directory, _ = backup
    (directory / "database.dump").write_bytes(b"modified")
    with pytest.raises(ValueError, match="CHECKSUM"):
        metadata.verify_backup(directory, IMAGE, "restore-project")


def test_configuration_bytes_drift_rejected_before_restore(backup):
    directory, _ = backup
    (metadata.CONFIG_DIRECTORY / "policy.json").write_text(
        '{"synthetic":"changed"}', encoding="utf-8"
    )
    with pytest.raises(ValueError, match="BACKUP_CONFIGURATION_MISMATCH"):
        metadata.verify_backup(directory, IMAGE, "restore-project")


@pytest.mark.parametrize("field", ["configuration", "descriptor"])
def test_process_identity_drift_refused(backup, field):
    directory, _ = backup
    worker = json.loads((directory / "worker.json").read_text())
    worker[field] = "changed"
    (directory / "worker.json").write_text(json.dumps(worker), encoding="utf-8")
    with pytest.raises(ValueError, match="API_WORKER_IDENTITY_MISMATCH"):
        metadata.identity(directory)


def test_log_summary_drops_secret_payloads_even_in_code_field(monkeypatch, capsys):
    monkeypatch.setattr(metadata.sys, "argv", ["metadata.py", "logs"])
    monkeypatch.setattr(
        metadata.sys,
        "stdin",
        io.StringIO(
            'raw private payload\n{"code":"VERY_PRIVATE_TOKEN"}\n{"code":"API_UNREADY","password":"private"}\n'
        ),
    )
    assert metadata.main() == 0
    output = capsys.readouterr().out
    assert "private" not in output and "VERY_PRIVATE_TOKEN" not in output
    assert json.loads(output)["codes"] == {"API_UNREADY": 1}


def test_invalid_command_does_not_echo_arguments(monkeypatch, capsys):
    monkeypatch.setattr(metadata.sys, "argv", ["metadata.py", "private-secret-command"])
    assert metadata.main() == 1
    output = capsys.readouterr()
    assert "private-secret" not in output.out + output.err


@pytest.mark.parametrize(
    "name",
    [
        "preflight",
        "install",
        "start",
        "status",
        "logs",
        "stop",
        "backup",
        "restore",
        "rollback",
    ],
)
def test_executable_entrypoints_reject_missing_arguments(name):
    shell = shutil.which("sh") or "C:/Program Files/Git/bin/bash.exe"
    path = HERE / (name + ".sh")
    assert (
        subprocess.run(
            [shell, "-n", str(path)], capture_output=True, check=False
        ).returncode
        == 0
    )
    result = subprocess.run([shell, str(path)], capture_output=True, check=False)
    assert result.returncode != 0 and b"ARGUMENTS_REQUIRED" in result.stderr


def test_required_ci_runs_actual_shell_recovery_against_sealed_image():
    workflow = yaml.safe_load(
        (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    )
    for name in ("full_validation", "solver_validation"):
        steps = [
            s
            for s in workflow["jobs"][name]["steps"]
            if "infra/enterprise/scripts/verify_container.py" in s.get("run", "")
        ]
        assert len(steps) == 1 and not steps[0].get("continue-on-error")
        assert (
            "--report build/validation/ci-enterprise-image-operations.json"
            in steps[0]["run"]
        )


def test_same_version_identity_is_not_merely_kit_version(backup):
    directory, doc = backup
    altered = deepcopy(doc["identity"])
    altered["descriptor"]["runtime_resolution"]["developer_kit_fingerprint"] = (
        "other-kit-bytes"
    )
    for name in ("api", "worker"):
        (directory / (name + ".json")).write_text(json.dumps(altered), encoding="utf-8")
    with pytest.raises(ValueError, match="BACKUP_DESCRIPTOR_MISMATCH"):
        metadata.verify_backup(directory, IMAGE, "restore-project")


def test_unreadable_directory_fails_before_docker_without_private_path(tmp_path):
    shell = shutil.which("sh") or "C:/Program Files/Git/bin/bash.exe"
    stubs = tmp_path / "tools"
    stubs.mkdir()
    for name, code in {
        "uname": 'if [ "$1" = -s ]; then echo Linux; else echo x86_64; fi',
        "find": "echo private-directory-name >&2; exit 1",
        "docker": "echo DOCKER_MUST_NOT_RUN >&2; exit 97",
    }.items():
        path = stubs / name
        path.write_text("#!/bin/sh\n" + code + "\n", encoding="utf-8", newline="\n")
        path.chmod(0o755)
    slot = tmp_path.as_posix()
    if os.name == "nt":
        slot = "/" + slot[0].lower() + slot[2:]
    wrapper = tmp_path / "gate.sh"
    wrapper.write_text(
        '#!/bin/sh\nPATH="' + slot + '/tools:$PATH"\nexport PATH\nexec /bin/sh "$@"\n',
        encoding="utf-8",
        newline="\n",
    )
    result = subprocess.run(
        [
            shell,
            wrapper.as_posix(),
            (HERE / "common.sh").as_posix(),
            "preflight",
            "/unused",
            "0" * 64,
            IMAGE,
            slot,
            "p826-test",
            "18000",
            "standalone",
        ],
        capture_output=True,
        check=False,
    )
    assert result.returncode != 0
    assert b"DIRECTORY_UNREADABLE" in result.stderr
    assert (
        b"private-directory-name" not in result.stderr
        and b"DOCKER_MUST_NOT_RUN" not in result.stderr
    )
