"""Routing and evidence rejection tests, without executing historical phase gates."""

import json
import subprocess
from types import SimpleNamespace
from typing import cast

import pytest

from scripts import ci_execution as ci


@pytest.fixture
def repository(tmp_path, monkeypatch):
    def git(*args):
        return subprocess.check_output(
            ["git", "-c", "user.name=CI Test", "-c", "user.email=ci@example.invalid", *args],
            cwd=tmp_path, text=True,
        ).strip()

    git("init", "-q")
    for name in ("uv.lock", "frontend/package-lock.json", ".github/workflows/ci.yml", "README.md", "frontend/src/App.tsx"):
        file = tmp_path / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text("baseline\n", encoding="utf-8")
    git("add", ".")
    git("commit", "-qm", "baseline")
    base = git("rev-parse", "HEAD")
    monkeypatch.setenv("GITHUB_SHA", base)
    monkeypatch.setenv("GITHUB_RUN_ID", "123")
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "1")
    return tmp_path, git, base


@pytest.mark.parametrize(("path", "selected"), [
    ("README.md", ["docs_validation"]),
    ("frontend/src/App.tsx", ["full_preflight", "frontend_validation"]),
    ("frontend/package-lock.json", list(ci.CURRENT)),
    ("backend/app/api.py", list(ci.CURRENT)),
    ("schemas/new.json", list(ci.CURRENT)),
    ("scripts/check.py", list(ci.CURRENT)),
    ("unknown.txt", list(ci.CURRENT)),
])
def test_changed_paths_select_only_proven_coverage(repository, path, selected):
    root, git, base = repository
    file = root / path
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text("changed\n", encoding="utf-8")
    git("add", ".")
    git("commit", "-qm", "change")
    value = ci.plan(root, base, git("rev-parse", "HEAD"))
    assert value["selected"] == selected
    ci.validate_plan(value, git("rev-parse", "HEAD"))


@pytest.mark.parametrize("operation", ["delete", "rename", "mixed", "empty", "bad-base", "audit"])
def test_uncertain_or_explicit_audit_expands(repository, operation):
    root, git, base = repository
    if operation == "delete":
        git("rm", "frontend/src/App.tsx")
    elif operation == "rename":
        git("mv", "frontend/src/App.tsx", "frontend/src/Renamed.tsx")
    elif operation == "mixed":
        (root / "frontend/src/App.tsx").write_text("new")
        (root / "unknown.txt").write_text("new")
    git("add", ".")
    git("commit", "--allow-empty", "-qm", "change")
    value = ci.plan(root, "unavailable" if operation == "bad-base" else base, git("rev-parse", "HEAD"), operation == "audit")
    assert set(value["selected"]) == ({"full_preflight", "full_backend", "full_operations", "full_validation"} if operation == "audit" else set(ci.CURRENT))


def complete_evidence(repository):
    root, _, base = repository
    value = ci.plan(root, base, base)
    downloads = root / "downloads"
    downloads.mkdir()
    for job in value["selected"]:
        file = root / "build/validation" / f"{job}.txt"
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text("actual evidence")
        destination = downloads / job
        destination.mkdir()
        (destination / file.name).write_bytes(file.read_bytes())
        files = [file]
        if job in {"solver_validation", "full_validation"}:
            from tests.enterprise.test_acceptance import write_evidence_pair
            extra = write_evidence_pair(root / "build/validation", base)
            for artifact in extra:
                (destination / artifact.name).write_bytes(artifact.read_bytes())
            files.extend(extra)
        ci.write(destination / f"ci-seal-{job}.json", ci.seal(root, job, files))
    needs = {job: {"result": result} for job, result in value["expected_jobs"].items() if job != "validate"}
    return root, value, needs, downloads


def test_complete_selected_evidence_passes(repository):
    assert ci.aggregate(*complete_evidence(repository))["result"] == "PASS"


def test_same_basename_in_different_report_directories_is_unambiguous(repository):
    root, _, _ = repository
    files = []
    downloads = root / "downloads"
    for directory in ("validation", "benchmarks"):
        file = root / "build" / directory / "same.json"
        ci.write(file, {"result": "PASS", "kind": directory})
        destination = downloads / directory / file.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(file.read_bytes())
        files.append(file)
    from tests.enterprise.test_acceptance import write_evidence_pair
    for artifact in write_evidence_pair(root / "build/validation", ci.identity()["head_sha"]):
        (downloads / "validation" / artifact.name).write_bytes(artifact.read_bytes())
        files.append(artifact)
    ci.write(downloads / "validation/ci-seal-solver_validation.json", ci.seal(root, "solver_validation", files))
    assert ci.verify_seal(root, downloads, "solver_validation")["files"][0]["path"] == "validation/same.json"
    # A valid report with the same name cannot substitute for the missing one.
    (downloads / "benchmarks/same.json").unlink()
    with pytest.raises(ValueError, match="benchmarks/same.json"):
        ci.verify_seal(root, downloads, "solver_validation")


@pytest.mark.parametrize("failure", ["skipped", "cancelled", "failure", "missing-job", "missing-seal", "missing-report", "corruption", "wrong-sha", "wrong-run", "wrong-attempt", "wrong-input", "plan-tamper"])
def test_aggregate_rejects_missing_failed_or_stale_evidence(repository, failure):
    root, value, needs, downloads = complete_evidence(repository)
    job = value["selected"][0]
    seal_path = downloads / job / f"ci-seal-{job}.json"
    seal = json.loads(seal_path.read_text())
    if failure in {"skipped", "cancelled", "failure"}:
        needs[job]["result"] = failure
    elif failure == "missing-job":
        del needs[job]
    elif failure == "missing-seal":
        seal_path.unlink()
    elif failure == "missing-report":
        (downloads / job / f"{job}.txt").unlink()
    elif failure == "corruption":
        (downloads / job / f"{job}.txt").write_text("tampered")
    elif failure == "plan-tamper":
        value["selected"].pop()
    else:
        key = {"wrong-sha": "head_sha", "wrong-run": "run_id", "wrong-attempt": "run_attempt", "wrong-input": "inputs"}[failure]
        seal[key] = "wrong"
        ci.write(seal_path, seal)
    with pytest.raises(ValueError):
        ci.aggregate(root, value, needs, downloads)


def test_repository_phase_suites_are_explicit():
    import conftest

    ordinary = SimpleNamespace(args=[str(p) for p in conftest.FULL_BACKEND_SUITES], getoption=lambda _: False)
    conftest.pytest_configure(cast(pytest.Config, ordinary))
    assert len(ordinary.args) == len(conftest.FULL_BACKEND_SUITES)
    audit = SimpleNamespace(args=list(ordinary.args), getoption=lambda _: True)
    conftest.pytest_configure(cast(pytest.Config, audit))
    assert set(audit.args) - set(ordinary.args) == {str(p) for p in conftest.REPOSITORY_EVIDENCE_TESTS}


def test_invalid_head_never_produces_plan(repository):
    root, _, base = repository
    with pytest.raises((ValueError, RuntimeError)):
        ci.plan(root, base, "missing-head")


@pytest.mark.parametrize(("suffix", "content"), [
    (".json", '{"result":"FAIL"}'),
    (".json", '{"result":"PASS","issues":["unresolved"]}'),
    (".xml", '<testsuite tests="1" failures="1"><testcase><failure/></testcase></testsuite>'),
    (".xml", '<testsuite tests="1" skipped="1"/>'),
    (".xml", '<testsuite tests="0"/>'),
])
def test_successful_job_cannot_seal_failed_or_empty_tests(repository, suffix, content):
    root, _, _ = repository
    file = root / ("bad" + suffix)
    file.write_text(content)
    with pytest.raises(ValueError):
        ci.seal(root, "full_backend", [file])


@pytest.mark.parametrize("product_drift", [False, True])
def test_frozen_runtime_metadata_staging_never_restores_product(repository, monkeypatch, product_drift):
    root, git, base = repository
    target = root / "infra/operations/non-production-target.v1.json"
    ci.write(target, {"release": {"implementation_sha": base}})
    (root / "README.md").write_text("later delivery prose")
    product = root / "backend/app/new.py"
    if product_drift:
        product.parent.mkdir(parents=True)
        product.write_text("new product code")
    git("add", ".")
    git("commit", "-qm", "later documentation")
    monkeypatch.setenv("GITHUB_SHA", git("rev-parse", "HEAD"))
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    if product_drift:
        with pytest.raises(ValueError, match="Runtime source drift"):
            ci.prepare_runtime(root)
        assert product.read_text() == "new product code"
        assert (root / "README.md").read_text() == "later delivery prose"
    else:
        report = ci.prepare_runtime(root)
        assert report["runtime_source_sha"] == base
        assert (root / "README.md").read_text() == "baseline\n"
        git("restore", "--source", "HEAD", "--worktree", "--", "README.md")
        assert (root / "README.md").read_text() == "later delivery prose"


def test_frozen_preparation_is_not_a_local_checkout_operation(repository, monkeypatch):
    root, _, _ = repository
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    with pytest.raises(ValueError, match="ephemeral Actions"):
        ci.prepare_runtime(root)


@pytest.mark.parametrize("job", ["solver_validation", "full_validation"])
def test_required_clean_acceptance_cannot_be_omitted(repository, job):
    root, _, _ = repository
    path = root / "build/validation/other.json"
    ci.write(path, {"status": "PASS"})
    with pytest.raises(ValueError, match="clean acceptance"):
        ci.seal(root, job, [path])


@pytest.mark.parametrize("outcome", ["pass", "missing", "failure", "drift", "exception"])
def test_historical_operations_replay_isolated_and_fail_closed(repository, monkeypatch, outcome):
    from scripts import p8_operations_check as operations

    root, git, _ = repository
    (root / ".gitignore").write_text("build/\n", encoding="utf-8")
    product = root / "backend/app/core.py"
    product.parent.mkdir(parents=True)
    product.write_text("frozen code\n", encoding="utf-8")
    git("add", ".")
    git("commit", "-qm", "frozen runtime")
    source = git("rev-parse", "HEAD")
    ci.write(root / operations.TARGET_PATH, {"release": {"implementation_sha": source}})
    product.write_text("current code\n", encoding="utf-8")
    added = root / "backend/app/new.py"
    added.write_text("current only\n", encoding="utf-8")
    (root / "README.md").write_text("current documentation\n", encoding="utf-8")
    git("add", ".")
    git("commit", "-qm", "current runtime")
    current = git("rev-parse", "HEAD")
    monkeypatch.setenv("GITHUB_SHA", current)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    observed = []

    def drill(arguments):
        from pathlib import Path

        replay = Path(arguments[arguments.index("--root") + 1])
        observed.append(replay)
        assert replay != root
        assert (replay / "backend/app/core.py").read_text() == "frozen code\n"
        assert not (replay / "backend/app/new.py").exists()
        assert product.read_text() == "current code\n"
        assert added.read_text() == "current only\n"
        if outcome == "exception":
            raise RuntimeError("drill crashed")
        for name in ("deployment", "observability", "recovery", "runbook"):
            if outcome == "missing" and name == "runbook":
                continue
            path = Path(arguments[arguments.index(f"--{name}-report") + 1])
            ci.write(path, {"status": "FAIL" if outcome == "failure" else "PASS", "issues": []})
        if outcome == "drift":
            (replay / "backend/app/core.py").write_text("tampered")
        return 0

    monkeypatch.setattr(operations, "main", drill)
    if outcome == "pass":
        report = ci.replay_operations(root)
        assert report["runtime_source_sha"] == source
        assert report["head_sha"] == report["driver_source_sha"] == current
        assert report["current_runtime_deployment_validated"] is False
        assert report["coverage"] == "DECLARED_HISTORICAL_P8_RUNTIME_ONLY"
        assert len(report["reports"]) == 4
        assert report["runtime_inputs_digest"] == ci.digest(report["runtime_inputs"])
    else:
        with pytest.raises((ValueError, RuntimeError, operations.OperationsEvidenceError)):
            ci.replay_operations(root)
    assert len(observed) == 1 and not observed[0].exists()
    assert product.read_text() == "current code\n"
    assert added.read_text() == "current only\n"
    assert (root / "README.md").read_text() == "current documentation\n"
    assert git("status", "--porcelain") == ""
    assert git("worktree", "list", "--porcelain").count("worktree ") == 1
    if outcome == "failure":
        saved = root / "build/validation/ci-p8-operations-deployment.json"
        assert json.loads(saved.read_text())["status"] == "FAIL"


@pytest.mark.parametrize("boundary", ["local", "identity", "dirty", "missing-target", "missing-source"])
def test_historical_operations_replay_rejects_before_driver(repository, monkeypatch, boundary):
    from scripts import p8_operations_check as operations

    root, git, base = repository
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    if boundary != "missing-target":
        ci.write(root / operations.TARGET_PATH, {"release": {
            "implementation_sha": "0" * 40 if boundary == "missing-source" else base,
        }})
        git("add", ".")
        git("commit", "-qm", "target")
    monkeypatch.setenv("GITHUB_SHA", git("rev-parse", "HEAD"))
    if boundary == "local":
        monkeypatch.delenv("GITHUB_ACTIONS")
    elif boundary == "identity":
        monkeypatch.setenv("GITHUB_SHA", "f" * 40)
    elif boundary == "dirty":
        (root / "README.md").write_text("local work")
    monkeypatch.setattr(operations, "main", lambda _: pytest.fail("driver must not run"))
    with pytest.raises((ValueError, RuntimeError, FileNotFoundError)):
        ci.replay_operations(root)
    assert git("worktree", "list", "--porcelain").count("worktree ") == 1
