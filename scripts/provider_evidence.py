"""Collect and verify exact GitHub Actions evidence for one implementation SHA."""

from __future__ import annotations

import argparse
import hashlib
import json
import posixpath
import re
import subprocess
import sys
import time
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Protocol, Sequence, cast

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.ci_execution import validate_plan

REPORT_VERSION = "provider-evidence-manifest.v1"
DEFAULT_WORKFLOW = "ci.yml"
DEFAULT_REQUIRED_CONTEXT = "validate"
DEFAULT_APP_ID = 15368
EXPECTED_NEGATIVE_GATE_VERDICT = "NOT_READY"
SHA_RE = re.compile(r"[0-9a-fA-F]{40}")
BLOCKER_ID_RE = re.compile(r"[A-Z0-9][A-Z0-9_-]+")
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
        "evidence_commit",
        "code_commit",
        "code_commit_sha",
    }
)
REQUIRED_FULL_ARTIFACT_PREFIXES = (
    "plantnexus-ci-profile-",
    "plantnexus-ci-preflight-",
    "plantnexus-ci-backend-",
    "plantnexus-ci-evidence-",
    "plantnexus-ci-operations-",
)
EXPECTED_FULL_JOB_CONCLUSIONS = {
    "classify": "success",
    "docs_validation": "skipped",
    "full_preflight": "success",
    "full_backend": "success",
    "full_validation": "success",
    "full_operations": "success",
    "validate": "success",
}
MAX_ARCHIVE_BYTES = 256 * 1024 * 1024
MAX_ENTRY_BYTES = 64 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 512 * 1024 * 1024


class ProviderClient(Protocol):
    """Provider calls required by the collector; fakeable for unit tests."""

    def list_runs(
        self, repository: str, workflow: str, commit_sha: str
    ) -> list[dict[str, Any]]: ...

    def check_runs(self, repository: str, commit_sha: str) -> list[dict[str, Any]]: ...

    def jobs(self, repository: str, run_id: int) -> list[dict[str, Any]]: ...

    def artifacts(self, repository: str, run_id: int) -> list[dict[str, Any]]: ...

    def download_artifact(self, repository: str, artifact_id: int) -> bytes: ...


class GhClient:
    """Thin gh CLI adapter that keeps authentication outside report payloads."""

    def __init__(self) -> None:
        self.read_retries: list[dict[str, Any]] = []

    def _read(self, args: Sequence[str]) -> bytes:
        for attempt in range(1, 4):
            result = subprocess.run(["gh", *args], check=False, capture_output=True)
            if result.returncode == 0:
                return result.stdout
            message = result.stderr.decode("utf-8", errors="replace").strip()
            transient = bool(re.search(r"HTTP (502|503|504)|connection reset|TLS handshake timeout|i/o timeout|unexpected EOF", message, re.IGNORECASE))
            if not transient or attempt == 3:
                raise RuntimeError(message or "gh read failed")
            # Record transport classification, never authentication headers or stderr.
            self.read_retries.append({"operation": args[0], "attempt": attempt, "reason": "transient-read-transport"})
            time.sleep(attempt)
        raise RuntimeError("gh read retry budget exhausted")

    def _json(self, *args: str) -> Any:
        data = self._read(args)
        try:
            return json.loads(data)
        except json.JSONDecodeError as error:
            raise RuntimeError(f"gh returned invalid JSON: {error}") from error

    def list_runs(
        self, repository: str, workflow: str, commit_sha: str
    ) -> list[dict[str, Any]]:
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
        return [
            cast(dict[str, Any], item) for item in payload if isinstance(item, dict)
        ]

    def check_runs(self, repository: str, commit_sha: str) -> list[dict[str, Any]]:
        payload = self._json(
            "api",
            "-H",
            "Accept: application/vnd.github+json",
            f"repos/{repository}/commits/{commit_sha}/check-runs?per_page=100",
        )
        if not isinstance(payload, dict) or not isinstance(
            payload.get("check_runs"), list
        ):
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
        if not isinstance(payload, dict) or not isinstance(
            payload.get("artifacts"), list
        ):
            raise RuntimeError("GitHub artifacts response is malformed")
        return [
            cast(dict[str, Any], item)
            for item in payload["artifacts"]
            if isinstance(item, dict)
        ]

    def download_artifact(self, repository: str, artifact_id: int) -> bytes:
        return self._read(
            [
                "api",
                "-H",
                "Accept: application/vnd.github+json",
                f"repos/{repository}/actions/artifacts/{artifact_id}/zip",
            ]
        )


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


def select_exact_run(
    runs: Sequence[Mapping[str, Any]], commit_sha: str
) -> dict[str, Any]:
    exact = [
        dict(run) for run in runs if str(run.get("headSha", "")).lower() == commit_sha
    ]
    if not exact:
        raise ValueError(f"no workflow run found for exact SHA {commit_sha}")
    if len(exact) != 1:
        identifiers = sorted(str(run.get("databaseId", "unknown")) for run in exact)
        raise ValueError(
            f"ambiguous workflow runs for exact SHA {commit_sha}: {identifiers}"
        )
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


def validate_json_payload(
    payload: object,
    commit_sha: str,
    entry_name: str,
    *,
    expected_gate_task_id: str | None = None,
    expected_gate_verdict: str | None = None,
) -> list[str]:
    issues: list[str] = []
    if not isinstance(payload, dict):
        return [f"{entry_name}: top-level JSON value must be an object"]
    gate_observation, gate_issues = inspect_expected_gate_payload(
        payload,
        commit_sha,
        entry_name,
        expected_gate_task_id=expected_gate_task_id,
        expected_gate_verdict=expected_gate_verdict,
    )
    issues.extend(gate_issues)
    for key in ("issues", "blocking_gaps", "blocking_issues"):
        value = payload.get(key)
        if isinstance(value, list) and value:
            if key == "blocking_gaps" and gate_observation is not None:
                continue
            issues.append(f"{entry_name}: $.{key} is non-empty")
    if payload.get("result") == "FAIL":
        issues.append(f"{entry_name}: $.result reports FAIL")
    if payload.get("status") == "FAIL":
        issues.append(f"{entry_name}: $.status reports FAIL")
    for key in IDENTITY_KEYS:
        value = payload.get(key)
        if (
            isinstance(value, str)
            and SHA_RE.fullmatch(value)
            and value.lower() != commit_sha
        ):
            issues.append(
                f"{entry_name}: $.{key} identity {value.lower()} does not match {commit_sha}"
            )
    git_identity = payload.get("git")
    if isinstance(git_identity, dict):
        value = git_identity.get("head_sha")
        if (
            isinstance(value, str)
            and SHA_RE.fullmatch(value)
            and value.lower() != commit_sha
        ):
            issues.append(
                f"{entry_name}: $.git.head_sha identity {value.lower()} does not match {commit_sha}"
            )
    return issues


def validate_gate_expectation(
    expected_gate_task_id: str | None,
    expected_gate_verdict: str | None,
) -> None:
    if (expected_gate_task_id is None) != (expected_gate_verdict is None):
        raise ValueError("expected gate task id and verdict must be provided together")
    if expected_gate_verdict not in {None, EXPECTED_NEGATIVE_GATE_VERDICT}:
        raise ValueError(
            "only the explicit NOT_READY negative Gate verdict may be expected"
        )
    if expected_gate_task_id is not None and not expected_gate_task_id.strip():
        raise ValueError("expected gate task id must not be empty")


def inspect_expected_gate_payload(
    payload: Mapping[str, Any],
    commit_sha: str,
    entry_name: str,
    *,
    expected_gate_task_id: str | None,
    expected_gate_verdict: str | None,
) -> tuple[dict[str, Any] | None, list[str]]:
    validate_gate_expectation(expected_gate_task_id, expected_gate_verdict)
    if expected_gate_task_id is None or payload.get("task_id") != expected_gate_task_id:
        return None, []
    report_version = payload.get("report_version")
    is_gate_candidate = (
        any(key in payload for key in ("verdict", "audit_status", "blocking_gaps"))
        or isinstance(report_version, str)
        and "gate-report" in report_version.lower()
    )
    if not is_gate_candidate:
        return None, []

    issues: list[str] = []
    if payload.get("verdict") != expected_gate_verdict:
        issues.append(
            f"{entry_name}: $.verdict does not match expected {expected_gate_verdict!r}"
        )
    if payload.get("audit_status") != "PASS":
        issues.append(f"{entry_name}: $.audit_status is not 'PASS'")
    if payload.get("validation_profile") != "PHASE_GATE":
        issues.append(f"{entry_name}: $.validation_profile is not 'PHASE_GATE'")
    if payload.get("code_commit") != commit_sha:
        issues.append(
            f"{entry_name}: $.code_commit does not match exact implementation SHA"
        )
    if not isinstance(report_version, str) or "gate" not in report_version.lower():
        issues.append(f"{entry_name}: $.report_version is not a Gate report")
    if payload.get("issues") != []:
        issues.append(f"{entry_name}: $.issues is not an empty list")

    blocking_gaps = payload.get("blocking_gaps")
    blocker_ids: list[str] = []
    if not isinstance(blocking_gaps, list) or not blocking_gaps:
        issues.append(
            f"{entry_name}: $.blocking_gaps must be a non-empty list for NOT_READY"
        )
    else:
        for index, blocker in enumerate(blocking_gaps):
            if not isinstance(blocker, dict):
                issues.append(
                    f"{entry_name}: $.blocking_gaps[{index}] must be an object"
                )
                continue
            blocker_id = blocker.get("blocker_id")
            if not isinstance(blocker_id, str) or not BLOCKER_ID_RE.fullmatch(
                blocker_id
            ):
                issues.append(
                    f"{entry_name}: $.blocking_gaps[{index}].blocker_id is invalid"
                )
            elif blocker_id in blocker_ids:
                issues.append(
                    f"{entry_name}: $.blocking_gaps[{index}].blocker_id is duplicated"
                )
            else:
                blocker_ids.append(blocker_id)
            if (
                not isinstance(blocker.get("summary"), str)
                or not blocker["summary"].strip()
            ):
                issues.append(
                    f"{entry_name}: $.blocking_gaps[{index}].summary is invalid"
                )

    checks = payload.get("checks")
    check_summary = payload.get("check_summary")
    if not isinstance(checks, list) or not isinstance(check_summary, dict):
        issues.append(f"{entry_name}: Gate checks or check summary is missing")
    else:
        observed_pass = sum(
            1
            for check in checks
            if isinstance(check, dict) and check.get("status") == "PASS"
        )
        observed_blocked = sum(
            1
            for check in checks
            if isinstance(check, dict) and check.get("status") == "BLOCKED"
        )
        invalid_checks = [
            index
            for index, check in enumerate(checks)
            if not isinstance(check, dict)
            or check.get("status") not in {"PASS", "BLOCKED"}
        ]
        expected_summary = {
            "check_count": len(checks),
            "pass_count": observed_pass,
            "blocked_count": observed_blocked,
            "error_count": 0,
        }
        if invalid_checks or any(
            check_summary.get(key) != value for key, value in expected_summary.items()
        ):
            issues.append(f"{entry_name}: $.check_summary does not match Gate checks")
        if isinstance(blocking_gaps, list) and observed_blocked != len(blocking_gaps):
            issues.append(f"{entry_name}: blocked checks do not match $.blocking_gaps")

    if issues:
        return None, issues
    return (
        {
            "task_id": expected_gate_task_id,
            "expected_verdict": expected_gate_verdict,
            "observed_verdict": payload["verdict"],
            "audit_status": payload["audit_status"],
            "report_version": report_version,
            "entry_path": entry_name,
            "blocking_gap_count": len(blocker_ids),
            "blocking_gap_ids": blocker_ids,
        },
        [],
    )


def inspect_artifact_zip(
    data: bytes,
    commit_sha: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    entries, issues, _ = _inspect_artifact_zip(
        data,
        commit_sha,
        expected_gate_task_id=None,
        expected_gate_verdict=None,
    )
    return entries, issues


def _inspect_artifact_zip(
    data: bytes,
    commit_sha: str,
    *,
    expected_gate_task_id: str | None = None,
    expected_gate_verdict: str | None = None,
) -> tuple[list[dict[str, Any]], list[str], list[dict[str, Any]]]:
    validate_gate_expectation(expected_gate_task_id, expected_gate_verdict)
    entries: list[dict[str, Any]] = []
    issues: list[str] = []
    gate_observations: list[dict[str, Any]] = []
    seen: set[str] = set()
    if len(data) > MAX_ARCHIVE_BYTES:
        return [], [f"artifact archive exceeds {MAX_ARCHIVE_BYTES} bytes"], []
    try:
        archive = zipfile.ZipFile(BytesIO(data))
    except zipfile.BadZipFile as error:
        return [], [f"artifact is not a valid ZIP: {error}"], []
    with archive:
        total_uncompressed = 0
        for info in archive.infolist():
            if info.is_dir():
                continue
            total_uncompressed += info.file_size
            if info.file_size > MAX_ENTRY_BYTES:
                issues.append(
                    f"ZIP entry exceeds {MAX_ENTRY_BYTES} bytes: {info.filename}"
                )
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
                    issues.extend(
                        validate_json_payload(
                            payload,
                            commit_sha,
                            name,
                            expected_gate_task_id=expected_gate_task_id,
                            expected_gate_verdict=expected_gate_verdict,
                        )
                    )
                    if isinstance(payload, dict):
                        observation, _ = inspect_expected_gate_payload(
                            payload,
                            commit_sha,
                            name,
                            expected_gate_task_id=expected_gate_task_id,
                            expected_gate_verdict=expected_gate_verdict,
                        )
                        if observation is not None:
                            gate_observations.append(observation)
    if not entries:
        issues.append("artifact ZIP contains no files")
    return (
        sorted(entries, key=lambda item: str(item["path"])),
        issues,
        gate_observations,
    )


def artifact_filename(artifact_id: int, name: str) -> str:
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip(".-") or "artifact"
    return f"{artifact_id}-{safe_name}.zip"


def ensure_required_artifacts(
    artifacts: Sequence[Mapping[str, Any]],
    prefixes: Sequence[str] = REQUIRED_FULL_ARTIFACT_PREFIXES,
) -> None:
    names = [str(artifact.get("name", "")) for artifact in artifacts]
    missing = [
        prefix
        for prefix in prefixes
        if not any(name.startswith(prefix) for name in names)
    ]
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


def summarize_full_jobs(
    jobs: Sequence[Mapping[str, Any]],
    expected: Mapping[str, str] = EXPECTED_FULL_JOB_CONCLUSIONS,
) -> list[dict[str, Any]]:
    by_name: dict[str, Mapping[str, Any]] = {}
    for job in jobs:
        name = str(job.get("name", ""))
        if name in by_name:
            raise ValueError(f"duplicate workflow job name: {name!r}")
        by_name[name] = job
    missing = sorted(set(expected) - set(by_name))
    if missing:
        raise ValueError(f"expected FULL jobs are missing: {missing}")
    records: list[dict[str, Any]] = []
    for name, expected_conclusion in expected.items():
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


def execution_plan_from_archive(data: bytes, commit_sha: str) -> dict[str, Any] | None:
    """Old runs retain their frozen FULL contract; new runs declare a strict plan."""
    _, issues = inspect_artifact_zip(data, commit_sha)
    if issues:
        raise ValueError("invalid profile archive: " + "; ".join(issues))
    with zipfile.ZipFile(BytesIO(data)) as archive:
        names = [n for n in archive.namelist() if PurePosixPath(n).name == "ci-execution-plan.json"]
        if not names:
            return None
        if len(names) != 1:
            raise ValueError("duplicate execution plan")
        value = json.loads(archive.read(names[0]))
    validate_plan(value, commit_sha)
    return value


def verify_execution_archives(
    plan: Mapping[str, Any], archives: Sequence[bytes], commit_sha: str, run_id: int,
) -> None:
    """Independently check aggregate and sealed bytes after ZIP safety inspection."""
    contents: dict[str, list[tuple[dict[str, bytes], str]]] = {}
    for data in archives:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            members = {safe_zip_name(name): archive.read(name) for name in archive.namelist() if not name.endswith("/")}
            for name in archive.namelist():
                if not name.endswith("/"):
                    contents.setdefault(PurePosixPath(name).name, []).append((members, name))
    aggregates = contents.get("ci-aggregate.json", [])
    if len(aggregates) != 1:
        raise ValueError("missing or duplicate CI aggregate")
    members, name = aggregates[0]
    aggregate = json.loads(members[name])
    if (aggregate.get("schema_version") != "ci-aggregate.v1"
            or aggregate.get("result") != "PASS"
            or aggregate.get("head_sha") != commit_sha
            or aggregate.get("run_id") != str(run_id)
            or aggregate.get("plan_digest") != plan["plan_digest"]
            or aggregate.get("selected") != plan["selected"]):
        raise ValueError("aggregate identity or selection mismatch")
    seals = []
    for job in plan["selected"]:
        matches = contents.get(f"ci-seal-{job}.json", [])
        if len(matches) != 1:
            raise ValueError(f"missing or duplicate seal: {job}")
        members, seal_name = matches[0]
        seal = json.loads(members[seal_name])
        if (seal.get("schema_version") != "ci-evidence-seal.v2" or seal.get("job") != job
                or any(seal.get(k) != aggregate.get(k) for k in ("head_sha", "run_id", "run_attempt"))
                or not seal.get("files")):
            raise ValueError(f"seal identity mismatch: {job}")
        for record in seal["files"]:
            path = safe_zip_name(record["path"])
            offset = posixpath.relpath(path, "validation")
            entry = safe_zip_name(posixpath.normpath(posixpath.join(posixpath.dirname(seal_name), offset)))
            data = members.get(entry)
            if data is None or hashlib.sha256(data).hexdigest() != record["sha256"]:
                raise ValueError(f"sealed evidence missing or corrupted: {path}")
        seals.append(seal)
    if aggregate.get("seals") != seals:
        raise ValueError("aggregate seals differ from producer evidence")


def wait_for_run(
    client: ProviderClient,
    repository: str,
    workflow: str,
    commit_sha: str,
    *,
    timeout_seconds: int,
    poll_seconds: int,
    requested_run_id: int | None = None,
) -> dict[str, Any]:
    if requested_run_id is not None and requested_run_id <= 0:
        raise ValueError("run ID must be positive")
    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            runs = client.list_runs(repository, workflow, commit_sha)
            if requested_run_id is not None:
                runs = [run for run in runs if run.get("databaseId") == requested_run_id]
            run = select_exact_run(runs, commit_sha)
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
            raise TimeoutError(
                f"timed out waiting for workflow run {run.get('databaseId')}"
            )
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
    expected_gate_task_id: str | None = None,
    expected_gate_verdict: str | None = None,
    requested_run_id: int | None = None,
) -> dict[str, Any]:
    validate_gate_expectation(expected_gate_task_id, expected_gate_verdict)
    observed_at = now or datetime.now(timezone.utc)
    run = wait_for_run(
        client,
        repository,
        workflow,
        commit_sha,
        timeout_seconds=timeout_seconds,
        poll_seconds=poll_seconds,
        requested_run_id=requested_run_id,
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
    artifacts = client.artifacts(repository, run_id)
    downloads: dict[int, bytes] = {}
    plan = None
    profiles = [a for a in artifacts if str(a.get("name", "")).startswith("plantnexus-ci-profile-")]
    if len(profiles) != 1:
        raise ValueError("expected exactly one profile artifact")
    profile = profiles[0]
    validate_artifact_metadata(profile, observed_at)
    downloads[profile["id"]] = client.download_artifact(repository, profile["id"])
    plan = execution_plan_from_archive(downloads[profile["id"]], commit_sha)
    job_records = summarize_full_jobs(
        client.jobs(repository, run_id), plan["expected_jobs"] if plan else EXPECTED_FULL_JOB_CONCLUSIONS,
    )
    prefixes = tuple(f"plantnexus-ci-{p}-" for p in plan["artifact_prefixes"]) if plan else REQUIRED_FULL_ARTIFACT_PREFIXES
    ensure_required_artifacts(artifacts, prefixes)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    artifact_records: list[dict[str, Any]] = []
    all_issues: list[str] = []
    gate_observations: list[dict[str, Any]] = []
    for artifact in sorted(artifacts, key=lambda item: str(item.get("name", ""))):
        name = str(artifact.get("name", ""))
        if not name.startswith("plantnexus-ci-"):
            continue
        artifact_id = artifact.get("id")
        if not isinstance(artifact_id, int) or not name:
            raise ValueError("artifact metadata is missing integer id or name")
        validate_artifact_metadata(artifact, observed_at)
        if artifact_id not in downloads:
            downloads[artifact_id] = client.download_artifact(repository, artifact_id)
        data = downloads[artifact_id]
        entries, issues, observations = _inspect_artifact_zip(
            data,
            commit_sha,
            expected_gate_task_id=expected_gate_task_id,
            expected_gate_verdict=expected_gate_verdict,
        )
        all_issues.extend(f"{name}: {issue}" for issue in issues)
        gate_observations.extend(
            {**observation, "artifact_name": name} for observation in observations
        )
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
    if expected_gate_task_id is not None and len(gate_observations) != 1:
        all_issues.append(
            "expected exactly one validated negative Gate report; "
            f"found {len(gate_observations)}"
        )
    if all_issues:
        raise ValueError("; ".join(all_issues))
    if plan:
        verify_execution_archives(plan, list(downloads.values()), commit_sha, run_id)
    report: dict[str, Any] = {
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
    if gate_observations:
        report["gate_expectation"] = gate_observations[0]
    if plan:
        report["execution_plan"] = plan
    if isinstance(client, GhClient):
        report["read_retries"] = client.read_retries
    return report


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
    expected_gate_task_id: str | None = None,
    expected_gate_verdict: str | None = None,
    requested_run_id: int | None = None,
) -> dict[str, Any] | None:
    validate_gate_expectation(expected_gate_task_id, expected_gate_verdict)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    if requested_run_id is not None:
        run_record = payload.get("run")
        if not isinstance(run_record, dict) or run_record.get("id") != requested_run_id:
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
    gate_expectation = payload.get("gate_expectation")
    if expected_gate_task_id is None:
        if gate_expectation is not None:
            return None
    elif (
        not isinstance(gate_expectation, dict)
        or gate_expectation.get("task_id") != expected_gate_task_id
        or gate_expectation.get("expected_verdict") != expected_gate_verdict
        or gate_expectation.get("observed_verdict") != expected_gate_verdict
        or gate_expectation.get("audit_status") != "PASS"
        or not isinstance(gate_expectation.get("blocking_gap_ids"), list)
        or not gate_expectation["blocking_gap_ids"]
        or gate_expectation.get("blocking_gap_count")
        != len(gate_expectation["blocking_gap_ids"])
    ):
        return None
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        return None
    observed_at = now or datetime.now(timezone.utc)
    replayed_gate_observations: list[dict[str, Any]] = []
    execution_archives: list[bytes] = []
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
            archive_data = archive_path.read_bytes()
            if hashlib.sha256(archive_data).hexdigest() != digest:
                return None
            if payload.get("execution_plan"):
                _, inspection_issues = inspect_artifact_zip(archive_data, commit_sha)
                if inspection_issues:
                    return None
                execution_archives.append(archive_data)
            if expected_gate_task_id is not None:
                _, inspection_issues, observations = _inspect_artifact_zip(
                    archive_data,
                    commit_sha,
                    expected_gate_task_id=expected_gate_task_id,
                    expected_gate_verdict=expected_gate_verdict,
                )
                if inspection_issues:
                    return None
                artifact_name = item.get("name")
                if not isinstance(artifact_name, str) or not artifact_name:
                    return None
                replayed_gate_observations.extend(
                    {**observation, "artifact_name": artifact_name}
                    for observation in observations
                )
        if payload.get("execution_plan"):
            validate_plan(payload["execution_plan"], commit_sha)
            summarize_full_jobs(payload["jobs"], payload["execution_plan"]["expected_jobs"])
            verify_execution_archives(payload["execution_plan"], execution_archives, commit_sha, payload["run"]["id"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if expected_gate_task_id is not None and (
        len(replayed_gate_observations) != 1
        or replayed_gate_observations[0] != gate_expectation
    ):
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
    parser.add_argument("--run-id", type=int, help="Explicitly select one run when the same SHA has multiple execution plans")
    parser.add_argument("--workflow", default=DEFAULT_WORKFLOW)
    parser.add_argument("--required-context", default=DEFAULT_REQUIRED_CONTEXT)
    parser.add_argument("--app-id", type=int, default=DEFAULT_APP_ID)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--artifacts-dir", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=1_200)
    parser.add_argument("--poll-seconds", type=int, default=20)
    parser.add_argument("--reuse", action="store_true")
    parser.add_argument("--expected-gate-task-id")
    parser.add_argument(
        "--expected-gate-verdict",
        choices=(EXPECTED_NEGATIVE_GATE_VERDICT,),
        help=(
            "accept one structurally valid PHASE_GATE report with the explicit "
            "NOT_READY verdict while preserving its blockers"
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root.resolve()
    report_path = args.report if args.report.is_absolute() else root / args.report
    artifacts_dir = (
        args.artifacts_dir
        if args.artifacts_dir.is_absolute()
        else root / args.artifacts_dir
    ).resolve()
    if not artifacts_dir.is_relative_to(root):
        print(
            "FAIL provider evidence: artifacts directory must remain inside repository",
            file=sys.stderr,
        )
        return 1
    try:
        validate_gate_expectation(
            args.expected_gate_task_id, args.expected_gate_verdict
        )
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
                expected_gate_task_id=args.expected_gate_task_id,
                expected_gate_verdict=args.expected_gate_verdict,
                requested_run_id=args.run_id,
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
            expected_gate_task_id=args.expected_gate_task_id,
            expected_gate_verdict=args.expected_gate_verdict,
            requested_run_id=args.run_id,
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
