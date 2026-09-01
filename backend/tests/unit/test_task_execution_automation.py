"""TEST-TASK-AUTOMATION-001 task execution automation tests."""

from __future__ import annotations

import hashlib
import json
import subprocess
import zipfile
from collections.abc import Mapping
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import pytest

from scripts.ci_preflight import (
    P4_FROZEN_BASE,
    frozen_isolation_sets,
    parse_name_status,
    validate_browser_and_working_directories,
    validate_frozen_isolation,
)
from scripts.provider_evidence import (
    REPORT_VERSION as PROVIDER_REPORT_VERSION,
    collect_evidence,
    load_reusable_manifest,
    repository_from_url,
    select_required_check,
    validate_json_payload,
)
from scripts.task_context_manifest import (
    REPORT_VERSION as CONTEXT_REPORT_VERSION,
    build_manifest,
)


TEST_ID = "TEST-TASK-AUTOMATION-001"
COMMIT_SHA = "a" * 40


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def write(root: Path, relative: str, text: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def context_repository(dependency_status: str = "done") -> tuple[TemporaryDirectory[str], Path, Path]:
    temporary = TemporaryDirectory()
    root = Path(temporary.name)
    git(root, "init")
    git(root, "config", "user.name", "PlantNexus Test")
    git(root, "config", "user.email", "plantnexus-test@example.invalid")
    for path in (
        "AGENTS.md",
        "docs/agents/AGENTS.md",
        "docs/current_phase.md",
        "docs/agents/reading-order-and-context-policy.md",
        "docs/agents/task-execution-protocol.md",
        "docs/quality/ci-gates-and-definition-of-done.md",
        "docs/quality/documentation-consistency-checks.md",
        "docs/architecture/configuration-environments-and-isolation.md",
    ):
        write(root, path, f"# {path}\n")
    write(
        root,
        "docs/tasks/P6/TASK-P6-04-dependency.md",
        "---\n"
        "doc_id: TASK-P6-04\n"
        f"status: {dependency_status}\n"
        "phase: P6\n"
        "---\n\n"
        "# dependency\n",
    )
    git(root, "add", "-A")
    git(root, "commit", "-m", "base")
    diff_base = git(root, "rev-parse", "HEAD")
    task_path = root / "docs/tasks/P6/TASK-P6-11-automation.md"
    write(
        root,
        task_path.relative_to(root).as_posix(),
        "---\n"
        "doc_id: TASK-P6-11\n"
        "status: in_progress\n"
        "phase: P6\n"
        "---\n\n"
        "# automation\n\n"
        "Depends on: TASK-P6-04\n\n"
        f"Diff base: {diff_base}\n\n"
        "Validation profile: HIGH_RISK\n\n"
        "Files allowed to change: `.github/workflows/ci.yml`\n\n"
        "Documents to update: `docs/architecture/configuration-environments-and-isolation.md`\n\n"
        "## Activation evidence\n\n"
        + ("historical payload " * 500),
    )
    return temporary, root, task_path


def test_context_manifest_is_bounded_and_soft_budget_never_truncates() -> None:
    temporary, root, task_path = context_repository()
    try:
        report = build_manifest(root, task_path, soft_char_budget=10)
    finally:
        temporary.cleanup()

    assert report["schema_version"] == CONTEXT_REPORT_VERSION
    assert report["result"] == "PASS"
    assert report["dependencies"][0]["status"] == "done"
    assert report["budget"]["over_budget"] is True
    assert report["warnings"]
    serialized = json.dumps(report)
    assert "historical payload" not in serialized
    assert "docs/current_phase.md" in {item["path"] for item in report["selection"]}


def test_context_manifest_fails_closed_for_unfinished_dependency() -> None:
    temporary, root, task_path = context_repository("in_progress")
    try:
        report = build_manifest(root, task_path)
    finally:
        temporary.cleanup()

    assert report["result"] == "FAIL"
    assert any("direct dependency is not done" in issue for issue in report["issues"])


def replay_workflow(*, remove_added: bool = True, restore_modified: bool = True) -> str:
    removed = (
        '            "${replay_root}/backend/tests/unit/new_test.py"\\\n'
        if remove_added
        else ""
    )
    restored = "            backend/app/service.py \\\n" if restore_modified else ""
    return (
        "      - name: TASK-P4-13 Dynamic replanning frontend machine evidence\n"
        "        run: |\n"
        "          rm -- \\\n"
        f"{removed}"
        "            \"${replay_root}/schemas/new.schema.json\"\n"
        "          git -C \"${replay_root}\" restore \\\n"
        f"            --source {P4_FROZEN_BASE} \\\n"
        "            -- \\\n"
        f"{restored}"
        "            pyproject.toml\n"
        "          mkdir -p \"${replay_root}/build\"\n"
        "      - name: P3 Gate Chromium replay 1\n"
        "        run: echo replay\n"
    )


def test_preflight_frozen_replay_matches_added_and_modified_paths() -> None:
    workflow = replay_workflow()
    removed, restored = frozen_isolation_sets(workflow)

    assert "backend/tests/unit/new_test.py" in removed
    assert "backend/app/service.py" in restored
    assert validate_frozen_isolation(
        {
            "backend/tests/unit/new_test.py": "A",
            "backend/app/service.py": "M",
            "docs/README.md": "M",
        },
        workflow,
    ) == []


def test_preflight_name_status_expands_rename_and_copy_for_isolation() -> None:
    assert parse_name_status(
        "R100\tbackend/app/old.py\tbackend/app/new.py\n"
        "C100\tbackend/tests/source.py\tbackend/tests/copy.py\n"
    ) == {
        "backend/app/old.py": "D",
        "backend/app/new.py": "A",
        "backend/tests/copy.py": "A",
    }


def test_preflight_frozen_replay_fails_for_unisolated_change() -> None:
    issues = validate_frozen_isolation(
        {
            "backend/tests/unit/new_test.py": "A",
            "backend/app/service.py": "M",
        },
        replay_workflow(remove_added=False, restore_modified=False),
    )

    assert {issue.path for issue in issues} == {
        "backend/tests/unit/new_test.py",
        "backend/app/service.py",
    }


def test_preflight_requires_single_worker_playwright_and_frontend_directory() -> None:
    workflow = (
        "      - name: Browser\n"
        "        run: npm exec -- playwright test\n"
        "      - name: Lint\n"
        "        run: npm run lint\n"
    )

    issues = validate_browser_and_working_directories(workflow)

    assert {issue.check_id for issue in issues} == {
        "PLAYWRIGHT-WORKERS",
        "WORKING-DIRECTORY",
    }


def zip_payload(payload: Mapping[str, Any], name: str = "report.json") -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(name, json.dumps(payload))
    return buffer.getvalue()


class FakeProviderClient:
    def __init__(self, payload: Mapping[str, Any] | None = None) -> None:
        self.payload = dict(payload or {"result": "PASS", "issues": []})
        self.downloads = 0

    def list_runs(self, repository: str, workflow: str, commit_sha: str) -> list[dict[str, Any]]:
        assert repository == "example/plantnexus"
        assert workflow == "ci.yml"
        return [
            {
                "databaseId": 42,
                "headSha": commit_sha,
                "status": "completed",
                "conclusion": "success",
                "url": "https://example.invalid/run/42",
                "createdAt": "2026-09-01T00:00:00Z",
                "updatedAt": "2026-09-01T00:05:00Z",
            }
        ]

    def check_runs(self, repository: str, commit_sha: str) -> list[dict[str, Any]]:
        return [
            {
                "id": 99,
                "name": "validate",
                "head_sha": commit_sha,
                "status": "completed",
                "conclusion": "success",
                "app": {"id": 15368},
                "details_url": "https://example.invalid/actions/runs/42/job/99",
            }
        ]

    def artifacts(self, repository: str, run_id: int) -> list[dict[str, Any]]:
        assert run_id == 42
        return [
            {
                "id": index,
                "name": f"{prefix}42",
                "expired": False,
                "expires_at": "2027-09-01T00:00:00Z",
            }
            for index, prefix in enumerate(
                (
                    "plantnexus-ci-profile-",
                    "plantnexus-ci-preflight-",
                    "plantnexus-ci-backend-",
                    "plantnexus-ci-evidence-",
                ),
                start=1,
            )
        ]

    def jobs(self, repository: str, run_id: int) -> list[dict[str, Any]]:
        conclusions = {
            "classify": "success",
            "docs_validation": "skipped",
            "full_preflight": "success",
            "full_backend": "success",
            "full_validation": "success",
            "validate": "success",
        }
        return [
            {
                "id": index,
                "name": name,
                "status": "completed",
                "conclusion": conclusion,
                "started_at": "2026-09-01T00:00:00Z",
                "completed_at": "2026-09-01T00:01:00Z",
            }
            for index, (name, conclusion) in enumerate(conclusions.items(), start=10)
        ]

    def download_artifact(self, repository: str, artifact_id: int) -> bytes:
        self.downloads += 1
        return zip_payload(self.payload, f"report-{artifact_id}.json")


def test_provider_collector_selects_exact_check_and_verifies_artifacts(tmp_path: Path) -> None:
    client = FakeProviderClient({"result": "PASS", "issues": [], "head_sha": COMMIT_SHA})

    report = collect_evidence(
        client,
        repository="example/plantnexus",
        workflow="ci.yml",
        commit_sha=COMMIT_SHA,
        required_context="validate",
        app_id=15368,
        artifacts_dir=tmp_path / "artifacts",
        timeout_seconds=0,
        poll_seconds=1,
        now=datetime(2026, 9, 1, tzinfo=timezone.utc),
    )

    assert report["schema_version"] == PROVIDER_REPORT_VERSION
    assert report["result"] == "PASS"
    assert report["run"]["id"] == 42
    assert len(report["jobs"]) == 6
    assert report["jobs"][0]["duration_seconds"] == 60.0
    assert len(report["artifacts"]) == 4
    assert client.downloads == 4
    assert all(len(item["sha256"]) == 64 for item in report["artifacts"])


def test_provider_collector_fails_for_reported_artifact_issues(tmp_path: Path) -> None:
    client = FakeProviderClient({"result": "FAIL", "issues": ["blocking"]})

    with pytest.raises(ValueError, match="non-empty|reports FAIL"):
        collect_evidence(
            client,
            repository="example/plantnexus",
            workflow="ci.yml",
            commit_sha=COMMIT_SHA,
            required_context="validate",
            app_id=15368,
            artifacts_dir=tmp_path,
            timeout_seconds=0,
            poll_seconds=1,
            now=datetime(2026, 9, 1, tzinfo=timezone.utc),
        )


def test_provider_required_check_rejects_wrong_app() -> None:
    with pytest.raises(ValueError, match="found 0"):
        select_required_check(
            [
                {
                    "name": "validate",
                    "head_sha": COMMIT_SHA,
                    "status": "completed",
                    "conclusion": "success",
                    "app": {"id": 1},
                }
            ],
            commit_sha=COMMIT_SHA,
            required_context="validate",
            app_id=15368,
        )


@pytest.mark.parametrize(
    "origin",
    (
        "git@github.com:example/plantnexus.git",
        "git@github-work:example/plantnexus.git",
        "https://github.com/example/plantnexus.git",
        "ssh://git@github.com/example/plantnexus.git",
    ),
)
def test_provider_repository_parser_accepts_git_host_alias(origin: str) -> None:
    assert repository_from_url(origin) == "example/plantnexus"


def test_provider_json_identity_checks_current_envelope_not_nested_history() -> None:
    wrong_sha = "b" * 40

    assert validate_json_payload(
        {"head_sha": wrong_sha, "issues": []}, COMMIT_SHA, "current.json"
    ) == [
        f"current.json: $.head_sha identity {wrong_sha} does not match {COMMIT_SHA}"
    ]
    assert (
        validate_json_payload(
            {"result": "PASS", "history": {"code_commit": wrong_sha}},
            COMMIT_SHA,
            "audit.json",
        )
        == []
    )


def test_provider_manifest_reuse_requires_matching_archive_digest(tmp_path: Path) -> None:
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    archive = zip_payload({"result": "PASS", "issues": []})
    archive_path = artifacts_dir / "1-evidence.zip"
    archive_path.write_bytes(archive)
    report_path = tmp_path / "provider.json"
    payload = {
        "schema_version": PROVIDER_REPORT_VERSION,
        "result": "PASS",
        "repository": "example/plantnexus",
        "workflow": "ci.yml",
        "implementation_sha": COMMIT_SHA,
        "run": {"id": 42},
        "required_check": {
            "name": "validate",
            "app_id": 15368,
            "conclusion": "success",
        },
        "artifacts": [
            {
                "archive_file": archive_path.name,
                "sha256": hashlib.sha256(archive).hexdigest(),
                "expires_at": "2027-09-01T00:00:00Z",
            }
        ],
    }
    report_path.write_text(json.dumps(payload), encoding="utf-8")

    reused = load_reusable_manifest(
        report_path,
        artifacts_dir,
        repository="example/plantnexus",
        workflow="ci.yml",
        commit_sha=COMMIT_SHA,
        required_context="validate",
        app_id=15368,
        now=datetime(2026, 9, 1, tzinfo=timezone.utc),
    )
    archive_path.write_bytes(b"tampered")
    rejected = load_reusable_manifest(
        report_path,
        artifacts_dir,
        repository="example/plantnexus",
        workflow="ci.yml",
        commit_sha=COMMIT_SHA,
        required_context="validate",
        app_id=15368,
        now=datetime(2026, 9, 1, tzinfo=timezone.utc),
    )

    assert reused is not None
    assert rejected is None
    assert TEST_ID == "TEST-TASK-AUTOMATION-001"
