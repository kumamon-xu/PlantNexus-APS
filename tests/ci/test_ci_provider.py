"""Provider accepts selected checks and refuses altered plan or missing evidence."""

import hashlib
from io import BytesIO
import json
import zipfile
from types import SimpleNamespace

import pytest

from scripts.ci_execution import ARTIFACTS, CURRENT, JOBS, VERSION, digest
from scripts.provider_evidence import execution_plan_from_archive, summarize_full_jobs, verify_execution_archives
from scripts.provider_evidence import GhClient


SHA = "a" * 40


def archive(files):
    stream = BytesIO()
    with zipfile.ZipFile(stream, "w") as output:
        for name, value in files.items():
            output.writestr(name, value if isinstance(value, bytes) else json.dumps(value))
    return stream.getvalue()


def plan(selected):
    value = {"schema_version": VERSION, "head_sha": SHA, "base_sha": "b" * 40,
             "audit": False, "selected": selected,
             "expected_jobs": {"classify": "success", **{j: "success" if j in selected else "skipped" for j in JOBS}, "validate": "success"},
             "artifact_prefixes": ["profile", *[ARTIFACTS[j] for j in selected], "aggregate"]}
    value["plan_digest"] = digest(value)
    return value


@pytest.mark.parametrize("selected", [["docs_validation"], ["full_preflight", "frontend_validation"], list(CURRENT)])
def test_dynamic_provider_jobs(selected):
    value = plan(selected)
    assert execution_plan_from_archive(archive({"ci-execution-plan.json": value}), SHA) == value
    jobs = [{"name": k, "conclusion": v} for k, v in value["expected_jobs"].items()]
    assert len(summarize_full_jobs(jobs, value["expected_jobs"])) == len(jobs)
    jobs[0]["conclusion"] = "skipped"
    with pytest.raises(ValueError):
        summarize_full_jobs(jobs, value["expected_jobs"])


def test_provider_preserves_legacy_profile():
    assert execution_plan_from_archive(archive({"ci-validation-profile.json": {"result": "PASS"}}), SHA) is None


def test_provider_rejects_forged_plan():
    value = plan(["docs_validation"])
    value["expected_jobs"]["full_backend"] = "success"
    with pytest.raises(ValueError):
        execution_plan_from_archive(archive({"ci-execution-plan.json": value}), SHA)


@pytest.mark.parametrize("failure", [None, "missing", "corrupt", "wrong-attempt", "wrong-plan"])
def test_provider_checks_sealed_bytes(failure):
    value = plan(["docs_validation"])
    seal = {"schema_version": "ci-evidence-seal.v1", "job": "docs_validation", "head_sha": SHA,
            "run_id": "123", "run_attempt": "1", "files": [{"name": "report.txt", "sha256": hashlib.sha256(b"ok").hexdigest()}]}
    aggregate = {"schema_version": "ci-aggregate.v1", "result": "PASS", "head_sha": SHA,
                 "run_id": "123", "run_attempt": "1", "plan_digest": value["plan_digest"],
                 "selected": value["selected"], "seals": [seal]}
    files = {"ci-seal-docs_validation.json": seal, "ci-aggregate.json": aggregate, "report.txt": b"ok"}
    if failure == "missing":
        del files["report.txt"]
    elif failure == "corrupt":
        files["report.txt"] = b"tampered"
    elif failure == "wrong-attempt":
        aggregate["run_attempt"] = "2"
    elif failure == "wrong-plan":
        aggregate["plan_digest"] = "invalid"
    if failure:
        with pytest.raises(ValueError):
            verify_execution_archives(value, [archive(files)], SHA, 123)
    else:
        verify_execution_archives(value, [archive(files)], SHA, 123)


@pytest.mark.parametrize(("message", "calls"), [(b"HTTP 503", 3), (b"HTTP 401", 1), (b"assertion failed", 1)])
def test_only_bounded_transport_reads_retry(monkeypatch, message, calls):
    observed = []

    def run(*args, **kwargs):
        observed.append(args)
        return SimpleNamespace(returncode=1, stderr=message)

    monkeypatch.setattr("scripts.provider_evidence.subprocess.run", run)
    monkeypatch.setattr("scripts.provider_evidence.time.sleep", lambda _: None)
    client = GhClient()
    with pytest.raises(RuntimeError):
        client._json("api", "repos/example/project/actions/runs")
    assert len(observed) == calls
    assert len(client.read_retries) == calls - 1


def test_transport_recovery_records_attempt_without_rerunning_jobs(monkeypatch):
    responses = iter([SimpleNamespace(returncode=1, stderr=b"HTTP 502"), SimpleNamespace(returncode=0, stdout=b'{}')])
    monkeypatch.setattr("scripts.provider_evidence.subprocess.run", lambda *a, **k: next(responses))
    monkeypatch.setattr("scripts.provider_evidence.time.sleep", lambda _: None)
    client = GhClient()
    assert client._json("api", "repos/example/project/actions/runs") == {}
    assert client.read_retries == [{"operation": "api", "attempt": 1, "reason": "transient-read-transport"}]
