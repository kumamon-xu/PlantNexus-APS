from copy import deepcopy
import json
from pathlib import Path

import pytest

from infra.enterprise.acceptance.report import CHECKS, validate


def evidence_pair(commit):
    images = {
        role: {"image_id": "sha256:" + str(i) * 64}
        for i, role in enumerate(("runtime", "database", "redis"), 1)
    }
    bundle = {
        "status": "PASS",
        "code_commit": commit,
        "images": images,
        **{
            key: "a" * 64
            for key in (
                "archive_sha256",
                "payload_fingerprint",
                "manifest_sha256",
                "checksums_sha256",
            )
        },
    }
    checks = []
    for mode in ("standalone", "enterprise"):
        for check in CHECKS:
            checks.append(
                {
                    "name": mode + "-" + check,
                    "status": "PASS",
                    "initial_images": 0,
                    "host_python": False,
                    "checkout": False,
                    "network": "none",
                    "engine": "27.5.1",
                    "certificate_verified": True,
                    "state": "COMPLETED",
                    "negative_rejected": True,
                    "schedule_state": "PUBLISHED",
                }
            )
    report = {
        "schema_version": "enterprise-clean-acceptance.v1",
        "task_id": "TASK-P8-28",
        "code_commit": commit,
        "status": "PASS",
        "verdict": "READY",
        "development": False,
        "production_ready": False,
        "issues": [],
        "candidate": {**bundle, "packaging_commit": commit},
        "checks": checks,
        "expected_check_count": len(checks),
        "commands": [{"argv": ["synthetic-test-only"]}],
    }
    return report, bundle


def write_evidence_pair(directory, commit):
    directory.mkdir(parents=True, exist_ok=True)
    report, bundle = evidence_pair(commit)
    paths = []
    for name, value in (("acceptance", report), ("bundle", bundle)):
        path = directory / ("ci-enterprise-image-" + name + ".json")
        path.write_text(json.dumps(value), encoding="utf-8")
        paths.append(path)
    return paths


@pytest.mark.parametrize(
    "mutation",
    [
        "none",
        "sha",
        "candidate-sha",
        "archive",
        "payload",
        "image",
        "missing",
        "duplicate",
        "skip",
        "blocked",
        "development",
        "ingress",
        "cached-store",
        "provider-missing",
    ],
)
def test_report_gate_rejects_incomplete_or_wrong_candidate(mutation):
    commit = "b" * 40
    report, bundle = evidence_pair(commit)
    report = deepcopy(report)
    if mutation == "sha":
        report["code_commit"] = "c" * 40
    if mutation == "candidate-sha":
        report["candidate"]["packaging_commit"] = "c" * 40
    if mutation == "archive":
        report["candidate"]["archive_sha256"] = "d" * 64
    if mutation == "payload":
        report["candidate"]["payload_fingerprint"] = "d" * 64
    if mutation == "image":
        report["candidate"]["images"]["runtime"]["image_id"] = "sha256:" + "d" * 64
    if mutation == "missing":
        report["checks"].pop()
    if mutation == "duplicate":
        report["checks"][1] = report["checks"][0]
    if mutation == "skip":
        report["checks"][0]["status"] = "SKIP"
    if mutation == "blocked":
        report["checks"][0]["status"] = "BLOCKED"
    if mutation == "development":
        report["development"] = True
    if mutation == "ingress":
        next(c for c in report["checks"] if c["name"] == "standalone-tls-health")[
            "certificate_verified"
        ] = False
    if mutation == "cached-store":
        report["checks"][0]["initial_images"] = 3
    if mutation == "provider-missing":
        report["commands"] = []
    if mutation == "none":
        validate(report, bundle, commit)
    else:
        with pytest.raises(ValueError):
            validate(report, bundle, commit)


def test_ci_requires_actual_clean_consumer_and_no_bypass():
    import yaml

    root = Path(__file__).resolve().parents[2]
    workflow = yaml.safe_load(
        (root / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    )
    for job in ("solver_validation", "full_validation"):
        steps = [
            s
            for s in workflow["jobs"][job]["steps"]
            if "scripts/enterprise_deployment_check.py" in s.get("run", "")
        ]
        assert (
            len(steps) == 1
            and not steps[0].get("if")
            and not steps[0].get("continue-on-error")
        )
        assert "--development" not in steps[0]["run"]
        assert (
            "--report build/validation/ci-enterprise-image-acceptance.json"
            in steps[0]["run"]
        )


def test_recovery_verifies_private_backup_without_host_access(tmp_path, monkeypatch):
    """Linux root-owned backup directories must not need build-user access."""
    import hashlib
    from subprocess import CompletedProcess
    from infra.enterprise.acceptance.runner import Consumer

    consumer = Consumer.__new__(Consumer)
    consumer.directory = tmp_path
    consumer.project = "p828-test"
    (tmp_path / "slot").mkdir()
    (tmp_path / "slot/validated.json").write_text("{}", encoding="utf-8")
    manifest = b"synthetic checksums\n"
    audit = b'{"reason":"CAPABILITY_DENIED"}\n'
    calls = []

    def invoke(action, *args, **kwargs):
        calls.append((action, args))

    def shell(command, *args):
        if command in {"cp", "test"}:
            return CompletedProcess([command, *args], 0, stdout=b"")
        assert command == "cat"
        (path,) = args
        payload = {
            "/audit/backup/SHA256SUMS": manifest,
            "/audit/backup/workspace-audit.jsonl": audit,
        }[path]
        return CompletedProcess([command, path], 0, stdout=payload)

    original = Path.read_bytes

    def private_read(path):
        if "backup" in path.parts:
            raise PermissionError("root-owned mode 0700 backup")
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", private_read)
    # Slot receipts are also root-owned; recovery must copy them in consumer.
    import shutil

    def private_copy(*args, **kwargs):
        raise PermissionError("root-owned validated receipt")

    monkeypatch.setattr(shutil, "copytree", private_copy)
    monkeypatch.setattr(consumer, "invoke", invoke)
    monkeypatch.setattr(consumer, "shell", shell)
    monkeypatch.setattr(consumer, "python", lambda *a, **kw: audit)
    monkeypatch.setattr(
        consumer, "http", lambda *a, **kw: {"state": "PUBLISHED", "export_job_id": "e"}
    )
    monkeypatch.setattr(consumer, "record", lambda *a, **kw: None)
    consumer.recovery("/synthetic", "e")
    for action in ("restore", "rollback"):
        args = next(args for name, args in calls if name == action)
        assert args[1] == hashlib.sha256(manifest).hexdigest()
