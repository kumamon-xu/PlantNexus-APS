"""Collect and verify exact GitHub Actions evidence for one implementation SHA."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Protocol, Sequence, cast


REPORT_VERSION = "provider-evidence-manifest.v1"
DEFAULT_WORKFLOW = "ci.yml"
DEFAULT_REQUIRED_CONTEXT = "validate"
DEFAULT_APP_ID = 15368
SHA_RE = re.compile(r"[0-9a-fA-F]{40}")
REPOSITORY_RE = re.compile(
    r"^(?:(?:https?://|ssh://git@)[^/]+/|git@[^:]+:)"
    r"(?P<repository>[^/\s]+/[^/\s]+?)(?:\.git)?$",
    re.IGNORECASE,
)
IDENTITY_KEYS = frozenset(
    {
        "git_head",
        "head_sha",
        "commit_sha",
        "implementation_sha",
        "code_commit",
        "code_commit_sha",
    }
)
REQUIRED_FULL_ARTIFACT_PREFIXES = (
    "plantnexus-ci-profile-",
    "plantnexus-ci-preflight-",
    "plantnexus-ci-backend-",
    "plantnexus-ci-evidence-",
)
EXPECTED_FULL_JOB_CONCLUSIONS = {
    "classify": "success",
    "docs_validation": "skipped",
    "full_preflight": "success",
    "full_backend": "success",
    "full_validation": "success",
    "validate": "success",
}
MAX_ARCHIVE_BYTES = 256 * 1024 * 1024
MAX_ENTRY_BYTES = 64 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 512 * 1024 * 1024


class ProviderClient(Protocol):
    """Provider calls required by the collector; fakeable for unit tests."""

    def list_runs(self, repository: str, workflow: str, commit_sha: str) -> list[dict[str, Any]]:
        ...

    def check_runs(self, repository: str, commit_sha: str) -> list[dict[str, Any]]:
        ...

    def jobs(self, repository: str, run_id: int) -> list[dict[str, Any]]:
        ...

    def artifacts(self, repository: str, run_id: int) -> list[dict[str, Any]]:
        ...

    def download_artifact(self, repository: str, artifact_id: int) -> bytes:
        ...


class GhClient:
    """Thin gh CLI adapter that keeps authentication outside report payloads."""

    def _json(self, *args: str) -> Any:
        result = subprocess.run(
            ["gh", *args],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "gh command failed")
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as error:
            raise RuntimeError(f"gh returned invalid JSON: {error}") from error

    def list_runs(self, repository: str, workflow: str, commit_sha: str) -> list[dict[str, Any]]:
        payload = self._json(
            "run",
            "list",
            "--repo",
            repository,
            "--workflow",
            workflow,
            "--commit",
            commit_sha,
            "--limit",
            "20",
            "--json",
            "databaseId,headSha,status,conclusion,workflowName,url,createdAt,updatedAt",
        )
        if not isinstance(payload, list):
            raise RuntimeError("gh run list returned a non-list payload")
        return [cast(dict[str, Any], item) for item in payload if isinstance(item, dict)]

    def check_runs(self, repository: str, commit_sha: str) -> list[dict[str, Any]]:
        payload = self._json(
            "api",
            "-H",
            "Accept: application/vnd.github+json",
            f"repos/{repository}/commits/{commit_sha}/check-runs?per_page=100",
        )
        if not isinstance(payload, dict) or not isinstance(payload.get("check_runs"), list):
            raise RuntimeError("GitHub check-runs response is malformed")
        return [
            cast(dict[str, Any], item)
            for item in payload["check_runs"]
            if isinstance(item, dict)
        ]

    def jobs(self, repository: str, run_id: int) -> list[dict[str, Any]]:
        payload = self._json(
            "api",
            "-H",
            "Accept: application/vnd.github+json",
            f"repos/{repository}/actions/runs/{run_id}/jobs?per_page=100",
        )
        if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
            raise RuntimeError("GitHub jobs response is malformed")
        return [
            cast(dict[str, Any], item)
            for item in payload["jobs"]
            if isinstance(item, dict)
        ]

    def artifacts(self, repository: str, run_id: int) -> list[dict[str, Any]]:
        payload = self._json(
            "api",
            "-H",
            "Accept: application/vnd.github+json",
            f"repos/{repository}/actions/runs/{run_id}/artifacts?per_page=100",
        )
        if not isinstance(payload, dict) or not isinstance(payload.get("artifacts"), list):
            raise RuntimeError("GitHub artifacts response is malformed")
        return [
            cast(dict[str, Any], item)
            for item in payload["artifacts"]
            if isinstance(item, dict)
        ]

    def download_artifact(self, repository: str, artifact_id: int) -> bytes:
        result = subprocess.run(
            [
                "gh",
                "api",
                "-H",
                "Accept: application/vnd.github+json",
                f"repos/{repository}/actions/artifacts/{artifact_id}/zip",
            ],
            check=False,
            capture_output=True,
        )
        if result.returncode != 0:
            message = result.stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(message or "artifact download failed")
        return result.stdout


def run_git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git command failed")
    return result.stdout.strip()


def resolve_head(root: Path, requested: str | None) -> str:
    head = run_git(root, "rev-parse", "HEAD").lower()
    if SHA_RE.fullmatch(head) is None:
        raise ValueError("HEAD is not a full commit SHA")
    if requested is None:
        return head
    if SHA_RE.fullmatch(requested) is None:
        raise ValueError("--commit must be a full 40-character SHA")
    resolved = run_git(root, "rev-parse", "--verify", f"{requested}^{{commit}}").lower()
    if resolved != head:
        raise ValueError("provider evidence may only be collected for checked-out HEAD")
    return resolved


def repository_from_url(origin: str) -> str:
    match = REPOSITORY_RE.search(origin)
    if match is None:
        raise ValueError("origin is not a recognizable GitHub repository URL")
    return match.group("repository")


def repository_from_origin(root: Path) -> str:
    return repository_from_url(run_git(root, "remote", "get-url", "origin"))


def parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def select_exact_run(runs: Sequence[Mapping[str, Any]], commit_sha: str) -> dict[str, Any]:
    exact = [dict(run) for run in runs if str(run.get("headSha", "")).lower() == commit_sha]
    if not exact:
        raise ValueError(f"no workflow run found for exact SHA {commit_sha}")
    if len(exact) != 1:
        identifiers = sorted(str(run.get("databaseId", "unknown")) for run in exact)
        raise ValueError(f"ambiguous workflow runs for exact SHA {commit_sha}: {identifiers}")
    return exact[0]


def select_required_check(
    checks: Sequence[Mapping[str, Any]],
    *,
    commit_sha: str,
    required_context: str,
    app_id: int,
    run_id: int | None = None,
) -> dict[str, Any]:
    exact: list[dict[str, Any]] = []
    for check in checks:
        app = check.get("app")
        observed_app_id = app.get("id") if isinstance(app, dict) else None
        details_url = str(check.get("details_url", ""))
        if (
            check.get("name") == required_context
            and str(check.get("head_sha", "")).lower() == commit_sha
            and observed_app_id == app_id
            and (run_id is None or f"/actions/runs/{run_id}/" in details_url)
        ):
            exact.append(dict(check))
    if len(exact) != 1:
        raise ValueError(
            f"expected exactly one {required_context!r} check from app {app_id}; found {len(exact)}"
        )
    check = exact[0]
    if check.get("status") != "completed" or check.get("conclusion") != "success":
        raise ValueError(
            f"required check is not successful: status={check.get('status')!r} "
            f"conclusion={check.get('conclusion')!r}"
        )
    return check


def safe_zip_name(value: str) -> str:
    normalized = value.replace("\\", "/")
    path = PurePosixPath(normalized)
    if (
        not normalized
        or normalized.startswith("/")
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ValueError(f"unsafe ZIP entry path: {value!r}")
    return path.as_posix()


def validate_json_payload(payload: object, commit_sha: str, entry_name: str) -> list[str]:
    issues: list[str] = []
    if not isinstance(payload, dict):
        return [f"{entry_name}: top-level JSON value must be an object"]
    for key in ("issues", "blocking_gaps", "blocking_issues"):
        value = payload.get(key)
        if isinstance(value, list) and value:
            issues.append(f"{entry_name}: $.{key} is non-empty")
    if payload.get("result") == "FAIL":
        issues.append(f"{entry_name}: $.result reports FAIL")
    for key in IDENTITY_KEYS:
        value = payload.get(key)
        if isinstance(value, str) and SHA_RE.fullmatch(value) and value.lower() != commit_sha:
            issues.append(
                f"{entry_name}: $.{key} identity {value.lower()} does not match {commit_sha}"
            )
    git_identity = payload.get("git")
    if isinstance(git_identity, dict):
        value = git_identity.get("head_sha")
        if isinstance(value, str) and SHA_RE.fullmatch(value) and value.lower() != commit_sha:
            issues.append(
                f"{entry_name}: $.git.head_sha identity {value.lower()} does not match {commit_sha}"
            )
    return issues


def inspect_artifact_zip(data: bytes, commit_sha: str) -> tuple[list[dict[str, Any]], list[str]]:
    entries: list[dict[str, Any]] = []
    issues: list[str] = []
    seen: set[str] = set()
    if len(data) > MAX_ARCHIVE_BYTES:
        return [], [f"artifact archive exceeds {MAX_ARCHIVE_BYTES} bytes"]
    try:
        archive = zipfile.ZipFile(BytesIO(data))
    except zipfile.BadZipFile as error:
        return [], [f"artifact is not a valid ZIP: {error}"]
    with archive:
        total_uncompressed = 0
        for info in archive.infolist():
            if info.is_dir():
                continue
            total_uncompressed += info.file_size
            if info.file_size > MAX_ENTRY_BYTES:
                issues.append(f"ZIP entry exceeds {MAX_ENTRY_BYTES} bytes: {info.filename}")
                continue
            if total_uncompressed > MAX_UNCOMPRESSED_BYTES:
                issues.append(
                    f"artifact uncompressed content exceeds {MAX_UNCOMPRESSED_BYTES} bytes"
                )
                break
            try:
                name = safe_zip_name(info.filename)
            except ValueError as error:
                issues.append(str(error))
                continue
            if name in seen:
                issues.append(f"duplicate ZIP entry: {name}")
                continue
            seen.add(name)
            content = archive.read(info)
            entry = {
                "path": name,
                "bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
            entries.append(entry)
            if name.lower().endswith(".json"):
                try:
                    payload = json.loads(content.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as error:
                    issues.append(f"{name}: invalid UTF-8 JSON: {error}")
                else:
                    issues.extend(validate_json_payload(payload, commit_sha, name))
    if not entries:
        issues.append("artifact ZIP contains no files")
    return sorted(entries, key=lambda item: str(item["path"])), issues


def artifact_filename(artifact_id: int, name: str) -> str:
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip(".-") or "artifact"
    return f"{artifact_id}-{safe_name}.zip"


def ensure_required_artifacts(artifacts: Sequence[Mapping[str, Any]]) -> None:
    names = [str(artifact.get("name", "")) for artifact in artifacts]
    missing = [prefix for prefix in REQUIRED_FULL_ARTIFACT_PREFIXES if not any(name.startswith(prefix) for name in names)]
    if missing:
        raise ValueError(f"required FULL artifacts are missing: {missing}")


def validate_artifact_metadata(artifact: Mapping[str, Any], now: datetime) -> None:
    if artifact.get("expired") is True:
        raise ValueError(f"artifact {artifact.get('name')!r} is expired")
    expires_at = parse_timestamp(artifact.get("expires_at"))
    if expires_at is None:
        raise ValueError(f"artifact {artifact.get('name')!r} has no valid expires_at")
    if expires_at <= now:
        raise ValueError(f"artifact {artifact.get('name')!r} has expired")


def summarize_full_jobs(jobs: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    by_name: dict[str, Mapping[str, Any]] = {}
    for job in jobs:
        name = str(job.get("name", ""))
        if name in by_name:
            raise ValueError(f"duplicate workflow job name: {name!r}")
        by_name[name] = job
    missing = sorted(set(EXPECTED_FULL_JOB_CONCLUSIONS) - set(by_name))
    if missing:
        raise ValueError(f"expected FULL jobs are missing: {missing}")
    records: list[dict[str, Any]] = []
    for name, expected_conclusion in EXPECTED_FULL_JOB_CONCLUSIONS.items():
        job = by_name[name]
        conclusion = job.get("conclusion")
        if conclusion != expected_conclusion:
            raise ValueError(
                f"job {name!r} conclusion {conclusion!r} is not {expected_conclusion!r}"
            )
        started_at = parse_timestamp(job.get("started_at"))
        completed_at = parse_timestamp(job.get("completed_at"))
        duration_seconds: float | None = None
        if started_at is not None and completed_at is not None:
            duration_seconds = max(0.0, (completed_at - started_at).total_seconds())
        records.append(
            {
                "id": job.get("id"),
                "name": name,
                "status": job.get("status"),
                "conclusion": conclusion,
                "started_at": job.get("started_at"),
                "completed_at": job.get("completed_at"),
                "duration_seconds": duration_seconds,
            }
        )
    return records


def wait_for_run(
    client: ProviderClient,
    repository: str,
    workflow: str,
    commit_sha: str,
    *,
    timeout_seconds: int,
    poll_seconds: int,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            run = select_exact_run(
                client.list_runs(repository, workflow, commit_sha), commit_sha
            )
        except ValueError as error:
            if not str(error).startswith("no workflow run found"):
                raise
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"timed out waiting for workflow run for {commit_sha}"
                ) from error
            time.sleep(max(1, poll_seconds))
            continue
        if run.get("status") == "completed":
            if run.get("conclusion") != "success":
                raise ValueError(
                    f"exact workflow run completed with {run.get('conclusion')!r}; do not rerun an old SHA"
                )
            return run
        if time.monotonic() >= deadline:
            raise TimeoutError(f"timed out waiting for workflow run {run.get('databaseId')}")
        time.sleep(max(1, poll_seconds))


def collect_evidence(
    client: ProviderClient,
    *,
    repository: str,
    workflow: str,
    commit_sha: str,
    required_context: str,
    app_id: int,
    artifacts_dir: Path,
    timeout_seconds: int,
    poll_seconds: int,
    now: datetime | None = None,
) -> dict[str, Any]:
    observed_at = now or datetime.now(timezone.utc)
    run = wait_for_run(
        client,
        repository,
        workflow,
        commit_sha,
        timeout_seconds=timeout_seconds,
        poll_seconds=poll_seconds,
    )
    run_id = run.get("databaseId")
    if not isinstance(run_id, int):
        raise ValueError("workflow run has no integer databaseId")
    check = select_required_check(
        client.check_runs(repository, commit_sha),
        commit_sha=commit_sha,
        required_context=required_context,
        app_id=app_id,
        run_id=run_id,
    )
    job_records = summarize_full_jobs(client.jobs(repository, run_id))
    artifacts = client.artifacts(repository, run_id)
    ensure_required_artifacts(artifacts)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    artifact_records: list[dict[str, Any]] = []
    all_issues: list[str] = []
    for artifact in sorted(artifacts, key=lambda item: str(item.get("name", ""))):
        name = str(artifact.get("name", ""))
        if not name.startswith("plantnexus-ci-"):
            continue
        artifact_id = artifact.get("id")
        if not isinstance(artifact_id, int) or not name:
            raise ValueError("artifact metadata is missing integer id or name")
        validate_artifact_metadata(artifact, observed_at)
        data = client.download_artifact(repository, artifact_id)
        entries, issues = inspect_artifact_zip(data, commit_sha)
        all_issues.extend(f"{name}: {issue}" for issue in issues)
        filename = artifact_filename(artifact_id, name)
        (artifacts_dir / filename).write_bytes(data)
        artifact_records.append(
            {
                "id": artifact_id,
                "name": name,
                "expires_at": artifact.get("expires_at"),
                "archive_file": filename,
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                "entries": entries,
            }
        )
    if all_issues:
        raise ValueError("; ".join(all_issues))
    return {
        "schema_version": REPORT_VERSION,
        "result": "PASS",
        "generated_at": observed_at.isoformat(),
        "repository": repository,
        "workflow": workflow,
        "implementation_sha": commit_sha,
        "run": {
            "id": run_id,
            "status": run.get("status"),
            "conclusion": run.get("conclusion"),
            "url": run.get("url"),
            "created_at": run.get("createdAt"),
            "updated_at": run.get("updatedAt"),
        },
        "required_check": {
            "name": required_context,
            "app_id": app_id,
            "status": check.get("status"),
            "conclusion": check.get("conclusion"),
            "id": check.get("id"),
        },
        "jobs": job_records,
        "artifacts": artifact_records,
        "issues": [],
    }


def load_reusable_manifest(
    path: Path,
    artifacts_dir: Path,
    *,
    repository: str,
    workflow: str,
    commit_sha: str,
    required_context: str,
    app_id: int,
    now: datetime | None = None,
) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    required_check = payload.get("required_check")
    if not isinstance(required_check, dict):
        return None
    if (
        payload.get("schema_version") != REPORT_VERSION
        or payload.get("result") != "PASS"
        or payload.get("repository") != repository
        or payload.get("workflow") != workflow
        or payload.get("implementation_sha") != commit_sha
        or required_check.get("name") != required_context
        or required_check.get("app_id") != app_id
        or required_check.get("conclusion") != "success"
    ):
        return None
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        return None
    observed_at = now or datetime.now(timezone.utc)
    try:
        for item in artifacts:
            if not isinstance(item, dict):
                return None
            validate_artifact_metadata(item, observed_at)
            archive_file = item.get("archive_file")
            digest = item.get("sha256")
            if not isinstance(archive_file, str) or not isinstance(digest, str):
                return None
            archive_path = artifacts_dir / archive_file
            if not archive_path.is_file():
                return None
            if hashlib.sha256(archive_path.read_bytes()).hexdigest() != digest:
                return None
    except (OSError, ValueError):
        return None
    return cast(dict[str, Any], payload)


def write_manifest(path: Path, root: Path, report: Mapping[str, Any]) -> None:
    resolved = path.resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError("report path must remain inside the repository")
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--repository")
    parser.add_argument("--commit")
    parser.add_argument("--workflow", default=DEFAULT_WORKFLOW)
    parser.add_argument("--required-context", default=DEFAULT_REQUIRED_CONTEXT)
    parser.add_argument("--app-id", type=int, default=DEFAULT_APP_ID)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--artifacts-dir", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=1_200)
    parser.add_argument("--poll-seconds", type=int, default=20)
    parser.add_argument("--reuse", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root.resolve()
    report_path = args.report if args.report.is_absolute() else root / args.report
    artifacts_dir = (
        args.artifacts_dir if args.artifacts_dir.is_absolute() else root / args.artifacts_dir
    ).resolve()
    if not artifacts_dir.is_relative_to(root):
        print("FAIL provider evidence: artifacts directory must remain inside repository", file=sys.stderr)
        return 1
    try:
        commit_sha = resolve_head(root, args.commit)
        repository = args.repository or repository_from_origin(root)
        if args.reuse:
            reusable = load_reusable_manifest(
                report_path,
                artifacts_dir,
                repository=repository,
                workflow=args.workflow,
                commit_sha=commit_sha,
                required_context=args.required_context,
                app_id=args.app_id,
            )
            if reusable is not None:
                print(
                    f"PASS provider evidence (reused): sha={commit_sha} "
                    f"run={reusable['run']['id']} artifacts={len(reusable['artifacts'])}"
                )
                return 0
        report = collect_evidence(
            GhClient(),
            repository=repository,
            workflow=args.workflow,
            commit_sha=commit_sha,
            required_context=args.required_context,
            app_id=args.app_id,
            artifacts_dir=artifacts_dir,
            timeout_seconds=args.timeout_seconds,
            poll_seconds=args.poll_seconds,
        )
        write_manifest(report_path, root, report)
    except (OSError, RuntimeError, TimeoutError, ValueError) as error:
        print(f"FAIL provider evidence: {error}", file=sys.stderr)
        return 1
    print(
        f"PASS provider evidence: sha={commit_sha} run={report['run']['id']} "
        f"artifacts={len(report['artifacts'])}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
