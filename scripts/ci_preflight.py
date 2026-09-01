"""Run dependency-free structural CI checks before the expensive FULL jobs."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence


REPORT_VERSION = "ci-preflight-report.v1"
P4_FROZEN_BASE = "d0a83c58cb4a2d4afa76e8c8cff08441574e2e30"
SHA_RE = re.compile(r"[0-9a-fA-F]{40}")
ROOT_MARKERS = (
    "pyproject.toml",
    "uv.lock",
    "frontend/package-lock.json",
    ".github/workflows/ci.yml",
)
GUARDED_PREFIXES = ("backend/app/", "backend/tests/", "schemas/")
GUARDED_EXACT = frozenset({"pyproject.toml"})


@dataclass(frozen=True, order=True)
class PreflightIssue:
    check_id: str
    path: str
    message: str


def normalize_repo_path(value: str) -> str:
    normalized = value.strip().replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    path = PurePosixPath(normalized)
    if (
        not normalized
        or normalized.startswith("/")
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ValueError(f"unsafe repository path: {value!r}")
    return path.as_posix()


def run_git(root: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", "-c", "core.quotepath=false", *args],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if check and result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git command failed")
    return result.stdout


def resolve_commit(root: Path, value: str) -> str:
    if SHA_RE.fullmatch(value) is None:
        raise ValueError(f"not a full commit SHA: {value!r}")
    resolved = run_git(root, "rev-parse", "--verify", f"{value}^{{commit}}").strip()
    if SHA_RE.fullmatch(resolved) is None:
        raise ValueError(f"commit did not resolve: {value}")
    return resolved.lower()


def parse_name_status(output: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in output.splitlines():
        if not line:
            continue
        fields = line.split("\t")
        status = fields[0]
        paths = fields[1:]
        if not paths or status[0] not in "ACDMRTUXB":
            raise ValueError(f"malformed git name-status line: {line!r}")
        kind = status[0]
        if kind == "R" and len(paths) == 2:
            result[normalize_repo_path(paths[0])] = "D"
            result[normalize_repo_path(paths[1])] = "A"
        elif kind == "C" and len(paths) == 2:
            result[normalize_repo_path(paths[1])] = "A"
        else:
            result[normalize_repo_path(paths[-1])] = kind
    return result


def changed_paths_from_base(root: Path, base_sha: str) -> dict[str, str]:
    changes = parse_name_status(
        run_git(root, "diff", "--name-status", "--find-renames=50%", base_sha, "--")
    )
    for path in run_git(root, "ls-files", "--others", "--exclude-standard").splitlines():
        if path.strip():
            changes[normalize_repo_path(path)] = "A"
    return dict(sorted(changes.items()))


def is_guarded_path(path: str) -> bool:
    return path in GUARDED_EXACT or path.startswith(GUARDED_PREFIXES)


def step_blocks(workflow_text: str) -> tuple[str, ...]:
    starts = [match.start() for match in re.finditer(r"(?m)^\s{6}- name:\s", workflow_text)]
    if not starts:
        return ()
    starts.append(len(workflow_text))
    return tuple(workflow_text[starts[index] : starts[index + 1]] for index in range(len(starts) - 1))


def frozen_replay_block(workflow_text: str) -> str:
    match = re.search(
        r"(?ms)^\s{6}- name: TASK-P4-13 Dynamic replanning frontend machine evidence\s*$"
        r"(?P<body>.*?)"
        r"(?=^\s{6}- name: P3 Gate Chromium replay 1\s*$)",
        workflow_text,
    )
    return match.group("body") if match is not None else ""


def frozen_isolation_sets(workflow_text: str) -> tuple[set[str], set[str]]:
    block = frozen_replay_block(workflow_text)
    if not block:
        return set(), set()
    rm_start = block.find("rm --")
    restore_start = block.find('git -C "${replay_root}" restore')
    mkdir_start = block.find("mkdir -p")
    rm_segment = block[rm_start:restore_start] if rm_start >= 0 and restore_start >= 0 else ""
    restore_segment = (
        block[restore_start:mkdir_start]
        if restore_start >= 0 and mkdir_start > restore_start
        else ""
    )
    removed = {
        normalize_repo_path(path)
        for path in re.findall(r'"\$\{replay_root\}/([^"\n]+)"', rm_segment)
    }
    restored = {
        normalize_repo_path(path.rstrip("\\"))
        for path in re.findall(
            r"(?<![/\w.-])((?:backend/(?:app|tests)|schemas)/[^\s\\]+|pyproject\.toml)",
            restore_segment,
        )
    }
    return removed, restored


def validate_root(root: Path) -> list[PreflightIssue]:
    issues: list[PreflightIssue] = []
    for marker in ROOT_MARKERS:
        if not (root / marker).is_file():
            issues.append(PreflightIssue("ROOT", marker, "required repository marker is missing"))
    try:
        inside = run_git(root, "rev-parse", "--is-inside-work-tree").strip()
    except RuntimeError as error:
        issues.append(PreflightIssue("ROOT", ".git", str(error)))
    else:
        if inside != "true":
            issues.append(PreflightIssue("ROOT", ".git", "root is not a Git working tree"))
    return issues


def validate_runtime_and_routing(workflow_text: str) -> list[PreflightIssue]:
    issues: list[PreflightIssue] = []
    required_fragments = {
        "python": 'python-version: "3.12"',
        "uv": 'version: "0.11.32"',
        "node": 'node-version: "24.19.0"',
        "npm": 'test "$(npm --version)" = "11.17.0"',
        "required-context": "  validate:",
        "fail-closed": "Enforce fail-closed validation routing",
        "utf8": 'PYTHONUTF8: "1"',
        "python-io-utf8": 'PYTHONIOENCODING: "utf-8"',
        "locale": "LANG: C.UTF-8",
    }
    for name, fragment in required_fragments.items():
        if fragment not in workflow_text:
            issues.append(
                PreflightIssue("RUNTIME-ROUTING", ".github/workflows/ci.yml", f"missing {name} contract: {fragment}")
            )
    if "continue-on-error" in workflow_text:
        issues.append(
            PreflightIssue(
                "FAIL-CLOSED",
                ".github/workflows/ci.yml",
                "continue-on-error is forbidden in the validation workflow",
            )
        )
    return issues


def validate_browser_and_working_directories(workflow_text: str) -> list[PreflightIssue]:
    issues: list[PreflightIssue] = []
    for block in step_blocks(workflow_text):
        name_match = re.search(r"(?m)^\s{6}- name:\s*(.+?)\s*$", block)
        name = name_match.group(1) if name_match is not None else "unnamed step"
        if ("playwright test" in block or "run test:e2e" in block) and "--workers=1" not in block:
            issues.append(
                PreflightIssue(
                    "PLAYWRIGHT-WORKERS",
                    ".github/workflows/ci.yml",
                    f"{name} does not pin --workers=1",
                )
            )
        if "npm " not in block:
            continue
        has_frontend_directory = "working-directory: frontend" in block or 'cd "${replay_root}/frontend"' in block
        npm_lines = [
            line.strip()
            for line in block.splitlines()
            if "npm " in line and "npm --version" not in line
        ]
        if any("--prefix frontend" not in line for line in npm_lines) and not has_frontend_directory:
            issues.append(
                PreflightIssue(
                    "WORKING-DIRECTORY",
                    ".github/workflows/ci.yml",
                    f"{name} has an npm command without a frontend prefix or working-directory",
                )
            )
    return issues


def validate_frozen_isolation(
    changes: Mapping[str, str], workflow_text: str
) -> list[PreflightIssue]:
    issues: list[PreflightIssue] = []
    block = frozen_replay_block(workflow_text)
    if not block:
        return [
            PreflightIssue(
                "FROZEN-REPLAY",
                ".github/workflows/ci.yml",
                "TASK-P4-13 frozen replay step is missing",
            )
        ]
    if f"--source {P4_FROZEN_BASE}" not in block:
        issues.append(
            PreflightIssue(
                "FROZEN-REPLAY",
                ".github/workflows/ci.yml",
                "P4 replay does not restore from the exact frozen base",
            )
        )
    removed, restored = frozen_isolation_sets(workflow_text)
    for path, status in sorted(changes.items()):
        if not is_guarded_path(path):
            continue
        if status == "A":
            if path not in removed:
                issues.append(
                    PreflightIssue(
                        "FROZEN-REPLAY",
                        path,
                        "post-frozen added path is not removed from the P4 replay",
                    )
                )
        elif path not in restored:
            issues.append(
                PreflightIssue(
                    "FROZEN-REPLAY",
                    path,
                    "post-frozen modified/deleted path is not restored in the P4 replay",
                )
            )
    return issues


def build_report(root: Path, *, ci_mode: bool = False) -> dict[str, Any]:
    root = root.resolve()
    issues = validate_root(root)
    workflow_path = root / ".github" / "workflows" / "ci.yml"
    workflow_text = workflow_path.read_text(encoding="utf-8") if workflow_path.is_file() else ""
    head_sha = ""
    base_sha = ""
    changes: dict[str, str] = {}
    try:
        head_sha = resolve_commit(root, run_git(root, "rev-parse", "HEAD").strip())
        base_sha = resolve_commit(root, P4_FROZEN_BASE)
        changes = changed_paths_from_base(root, base_sha)
    except (RuntimeError, ValueError) as error:
        issues.append(PreflightIssue("GIT-IDENTITY", ".git", str(error)))

    if workflow_text:
        issues.extend(validate_runtime_and_routing(workflow_text))
        issues.extend(validate_browser_and_working_directories(workflow_text))
        issues.extend(validate_frozen_isolation(changes, workflow_text))
    if ci_mode and os.environ.get("GITHUB_SHA"):
        github_sha = os.environ["GITHUB_SHA"].lower()
        if github_sha != head_sha:
            issues.append(
                PreflightIssue(
                    "GIT-IDENTITY",
                    ".git",
                    f"GITHUB_SHA {github_sha} does not match checked-out HEAD {head_sha}",
                )
            )

    unique_issues = sorted(set(issues))
    checks = []
    for check_id in (
        "ROOT",
        "GIT-IDENTITY",
        "RUNTIME-ROUTING",
        "FAIL-CLOSED",
        "WORKING-DIRECTORY",
        "PLAYWRIGHT-WORKERS",
        "FROZEN-REPLAY",
    ):
        checks.append(
            {
                "check_id": check_id,
                "status": "FAIL" if any(issue.check_id == check_id for issue in unique_issues) else "PASS",
            }
        )
    return {
        "schema_version": REPORT_VERSION,
        "result": "PASS" if not unique_issues else "FAIL",
        "git": {
            "head_sha": head_sha,
            "p4_frozen_base": base_sha,
            "guarded_change_count": sum(is_guarded_path(path) for path in changes),
        },
        "runtime": {
            "python": "3.12",
            "uv": "0.11.32",
            "node": "24.19.0",
            "npm": "11.17.0",
            "ci_mode": ci_mode,
        },
        "checks": checks,
        "issues": [asdict(issue) for issue in unique_issues],
        "warnings": [],
    }


def write_report(path: Path, root: Path, report: dict[str, Any]) -> None:
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
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--ci-mode", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root.resolve()
    report_path = args.report if args.report.is_absolute() else root / args.report
    try:
        report = build_report(root, ci_mode=args.ci_mode)
        write_report(report_path, root, report)
    except (OSError, RuntimeError, ValueError) as error:
        print(f"FAIL CI preflight: {error}", file=sys.stderr)
        return 1
    print(
        f"{report['result']} CI preflight: checks={len(report['checks'])} "
        f"issues={len(report['issues'])}"
    )
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
