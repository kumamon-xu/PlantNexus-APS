"""Routing and evidence rejection tests, without executing historical phase gates."""

import json
import subprocess
from types import SimpleNamespace

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
        file = downloads / f"{job}.txt"
        file.write_text("actual evidence")
        ci.write(downloads / f"ci-seal-{job}.json", ci.seal(root, job, [file]))
    needs = {job: {"result": result} for job, result in value["expected_jobs"].items() if job != "validate"}
    return root, value, needs, downloads


def test_complete_selected_evidence_passes(repository):
    assert ci.aggregate(*complete_evidence(repository))["result"] == "PASS"


@pytest.mark.parametrize("failure", ["skipped", "cancelled", "failure", "missing-job", "missing-seal", "missing-report", "corruption", "wrong-sha", "wrong-run", "wrong-attempt", "wrong-input", "plan-tamper"])
def test_aggregate_rejects_missing_failed_or_stale_evidence(repository, failure):
    root, value, needs, downloads = complete_evidence(repository)
    job = value["selected"][0]
    seal_path = downloads / f"ci-seal-{job}.json"
    seal = json.loads(seal_path.read_text())
    if failure in {"skipped", "cancelled", "failure"}:
        needs[job]["result"] = failure
    elif failure == "missing-job":
        del needs[job]
    elif failure == "missing-seal":
        seal_path.unlink()
    elif failure == "missing-report":
        (downloads / f"{job}.txt").unlink()
    elif failure == "corruption":
        (downloads / f"{job}.txt").write_text("tampered")
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
    conftest.pytest_configure(ordinary)
    assert len(ordinary.args) == len(conftest.FULL_BACKEND_SUITES)
    audit = SimpleNamespace(args=list(ordinary.args), getoption=lambda _: True)
    conftest.pytest_configure(audit)
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
