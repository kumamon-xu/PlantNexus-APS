"""Fail-closed CI validation profile routing and public Markdown checks."""

from __future__ import annotations

import argparse
import difflib
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Sequence
from urllib.parse import unquote, urlsplit


REPORT_VERSION = "ci-validation-profile.v1"
DOCS_REPORT_VERSION = "ci-public-docs-validation.v1"
FULL = "FULL"
DOCS_ONLY = "DOCS_ONLY"
SHA_RE = re.compile(r"[0-9a-fA-F]{40}")
LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
REFERENCE_LINK_RE = re.compile(r"^\s*\[[^\]]+\]:\s*(\S+)")
FENCE_RE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
PUBLIC_EVIDENCE_PATTERNS = (
    re.compile(
        r"(?i)\b(?:run|job|artifact)(?:[_ -]?(?:id|number))?\b.{0,48}\b\d{8,}\b"
    ),
    re.compile(r"(?i)\bsha256\s*[:=]\s*[0-9a-f]{64}\b"),
    re.compile(r"(?i)\b(?:implementation|closure)\b.{0,48}\b[0-9a-f]{40}\b"),
)

PUBLIC_MARKDOWN_EXACT = frozenset({"README.md", "docs/README.md"})
INTERNAL_DOC_EXACT = frozenset(
    {"docs/adr/ADR_TEMPLATE.md", "docs/core/APS_IMPLEMENTATION_SPEC.md"}
)
PUBLIC_MARKDOWN_PREFIXES = (
    "docs/adr/",
    "docs/architecture/",
    "docs/contracts/",
    "docs/core/",
    "docs/domain/",
    "docs/frontend/",
    "docs/operations/",
    "docs/planning/",
    "docs/simulation/",
)
INTERNAL_DOC_PREFIXES = (
    "docs/agents/",
    "docs/governance/",
    "docs/milestones/",
    "docs/quality/",
    "docs/runbooks/",
    "docs/tasks/",
)
NORMAL_BLOB_MODES = frozenset({"100644", "100755"})


@dataclass(frozen=True)
class ChangeEntry:
    status: str
    paths: tuple[str, ...]


@dataclass(frozen=True)
class Classification:
    profile: str
    reason: str
    base_sha: str
    head_sha: str
    entries: tuple[ChangeEntry, ...]
    checks: tuple[dict[str, object], ...]


@dataclass(frozen=True, order=True)
class DocsIssue:
    check_id: str
    path: str
    target: str
    message: str


class GitRepository:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def run(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            ["git", "-c", "core.quotepath=false", *args],
            cwd=self.root,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if check and result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "git command failed")
        return result

    def resolve_commit(self, value: str) -> str:
        if SHA_RE.fullmatch(value) is None:
            raise ValueError("commit identity is not a full 40-character SHA")
        resolved = self.run("rev-parse", "--verify", f"{value}^{{commit}}").stdout.strip()
        if SHA_RE.fullmatch(resolved) is None:
            raise ValueError("git did not resolve a full commit SHA")
        return resolved.lower()

    def is_ancestor(self, base_sha: str, head_sha: str) -> bool:
        return self.run(
            "merge-base", "--is-ancestor", base_sha, head_sha, check=False
        ).returncode == 0

    def changed_entries(self, base_sha: str, head_sha: str) -> tuple[ChangeEntry, ...]:
        output = self.run(
            "diff",
            "--name-status",
            "-z",
            "--find-renames=50%",
            f"{base_sha}..{head_sha}",
            "--",
        ).stdout
        return parse_name_status_z(output)

    def object_mode(self, revision: str, path: str) -> tuple[str, str] | None:
        output = self.run("ls-tree", "-z", revision, "--", path).stdout
        if not output:
            return None
        metadata, separator, listed_path = output.rstrip("\0").partition("\t")
        fields = metadata.split()
        if separator != "\t" or len(fields) != 3 or listed_path != path:
            raise ValueError(f"unexpected ls-tree result for {path}")
        mode, object_type, _object_sha = fields
        return mode, object_type

    def list_paths(self, revision: str) -> tuple[str, ...]:
        output = self.run("ls-tree", "-r", "--name-only", "-z", revision).stdout
        return tuple(path for path in output.split("\0") if path)

    def read_text(self, revision: str, path: str) -> str:
        return self.run("show", f"{revision}:{path}").stdout

    def object_exists(self, revision: str, path: str) -> bool:
        return self.run("cat-file", "-e", f"{revision}:{path}", check=False).returncode == 0


def normalize_repo_path(value: str) -> str:
    normalized = value.replace("\\", "/")
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


def parse_name_status_z(output: str) -> tuple[ChangeEntry, ...]:
    if not output:
        return ()
    tokens = output.split("\0")
    if tokens[-1] != "":
        raise ValueError("name-status output is not NUL terminated")
    tokens.pop()
    entries: list[ChangeEntry] = []
    index = 0
    while index < len(tokens):
        status = tokens[index]
        index += 1
        if not status or status[0] not in "ACDMRTUXB":
            raise ValueError(f"unknown git status: {status!r}")
        path_count = 2 if status[0] in {"R", "C"} else 1
        if index + path_count > len(tokens):
            raise ValueError(f"incomplete path list for git status {status!r}")
        paths = tuple(
            normalize_repo_path(value) for value in tokens[index : index + path_count]
        )
        index += path_count
        entries.append(ChangeEntry(status=status, paths=paths))
    return tuple(entries)


def is_public_markdown(path: str) -> bool:
    if not path.lower().endswith(".md"):
        return False
    if path in INTERNAL_DOC_EXACT:
        return False
    if path in PUBLIC_MARKDOWN_EXACT:
        return True
    return path.startswith(PUBLIC_MARKDOWN_PREFIXES)


def classify_entries(entries: Sequence[ChangeEntry]) -> tuple[str, str]:
    if not entries:
        return FULL, "empty diff cannot prove a documentation-only change"
    for entry in entries:
        if entry.status[0] not in "ACDMR":
            return FULL, f"git status {entry.status!r} requires full validation"
        for path in entry.paths:
            if not is_public_markdown(path):
                return FULL, f"path {path!r} is outside the public Markdown allow-list"
    return DOCS_ONLY, "every changed path is allow-listed public Markdown"


def _mode_checks(
    repository: GitRepository,
    entries: Sequence[ChangeEntry],
    base_sha: str,
    head_sha: str,
) -> tuple[bool, str]:
    for entry in entries:
        code = entry.status[0]
        revisions_and_paths: list[tuple[str, str]] = []
        if code == "D":
            revisions_and_paths.append((base_sha, entry.paths[0]))
        elif code in {"R", "C"}:
            revisions_and_paths.extend(
                ((base_sha, entry.paths[0]), (head_sha, entry.paths[1]))
            )
        else:
            revisions_and_paths.append((head_sha, entry.paths[0]))
        for revision, path in revisions_and_paths:
            object_mode = repository.object_mode(revision, path)
            if object_mode is None:
                return False, f"cannot prove Git object identity for {path!r}"
            mode, object_type = object_mode
            if object_type != "blob" or mode not in NORMAL_BLOB_MODES:
                return False, f"non-regular Git object {mode}/{object_type} at {path!r}"
    return True, "all changed documents are regular Git blobs"


def classify_repository(
    repository: GitRepository, base_value: str, head_value: str
) -> Classification:
    checks: list[dict[str, object]] = []
    try:
        base_sha = repository.resolve_commit(base_value)
        head_sha = repository.resolve_commit(head_value)
        checks.append({"check": "commit-identities", "passed": True})
    except (RuntimeError, ValueError) as error:
        checks.append(
            {"check": "commit-identities", "passed": False, "detail": str(error)}
        )
        return Classification(
            profile=FULL,
            reason="invalid or unavailable commit identity requires full validation",
            base_sha=base_value,
            head_sha=head_value,
            entries=(),
            checks=tuple(checks),
        )

    ancestor = repository.is_ancestor(base_sha, head_sha)
    checks.append({"check": "base-is-ancestor", "passed": ancestor})
    if not ancestor:
        return Classification(
            profile=FULL,
            reason="event base is not an ancestor of the head commit",
            base_sha=base_sha,
            head_sha=head_sha,
            entries=(),
            checks=tuple(checks),
        )

    try:
        entries = repository.changed_entries(base_sha, head_sha)
        profile, reason = classify_entries(entries)
        checks.append(
            {
                "check": "public-markdown-paths",
                "passed": profile == DOCS_ONLY,
                "detail": reason,
            }
        )
        if profile == DOCS_ONLY:
            modes_valid, mode_reason = _mode_checks(
                repository, entries, base_sha, head_sha
            )
            checks.append(
                {
                    "check": "regular-git-blobs",
                    "passed": modes_valid,
                    "detail": mode_reason,
                }
            )
            if not modes_valid:
                profile, reason = FULL, mode_reason
    except (RuntimeError, ValueError) as error:
        entries = ()
        profile = FULL
        reason = f"diff inspection failed closed: {error}"
        checks.append(
            {"check": "public-markdown-paths", "passed": False, "detail": str(error)}
        )

    return Classification(
        profile=profile,
        reason=reason,
        base_sha=base_sha,
        head_sha=head_sha,
        entries=entries,
        checks=tuple(checks),
    )


def _report_payload(classification: Classification) -> dict[str, Any]:
    return {
        "schema_version": REPORT_VERSION,
        "result": "PASS",
        "profile": classification.profile,
        "reason": classification.reason,
        "base_sha": classification.base_sha,
        "head_sha": classification.head_sha,
        "changed_entries": [asdict(entry) for entry in classification.entries],
        "checks": list(classification.checks),
        "issues": [],
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_github_output(path: Path, profile: str) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(f"profile={profile}\n")


def _clean_link_target(raw_target: str) -> str | None:
    target = raw_target.strip()
    if target.startswith("<") and ">" in target:
        target = target[1 : target.index(">")]
    else:
        target = target.split(maxsplit=1)[0]
    if not target or target.startswith("#") or target.startswith("//"):
        return None
    parsed = urlsplit(target)
    if parsed.scheme:
        if parsed.scheme.lower() in {"http", "https", "mailto", "tel"}:
            return None
        raise ValueError(f"unsupported link scheme {parsed.scheme!r}")
    if target.startswith("/"):
        raise ValueError("absolute links are outside the repository boundary")
    decoded = unquote(parsed.path)
    return decoded or None


def _resolve_link(source_path: str, target: str) -> str:
    combined = PurePosixPath(source_path).parent / PurePosixPath(target)
    parts: list[str] = []
    for part in combined.parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if not parts:
                raise ValueError("link escapes the repository root")
            parts.pop()
        else:
            parts.append(part)
    if not parts:
        raise ValueError("link does not identify a repository object")
    return PurePosixPath(*parts).as_posix()


def _document_issues(
    repository: GitRepository, revision: str, path: str, text: str
) -> set[DocsIssue]:
    issues: set[DocsIssue] = set()
    fence_character: str | None = None
    fence_length = 0
    for line_number, line in enumerate(text.splitlines(), start=1):
        fence_match = FENCE_RE.match(line)
        if fence_match is not None:
            marker = fence_match.group(1)
            if fence_character is None:
                fence_character = marker[0]
                fence_length = len(marker)
            elif marker[0] == fence_character and len(marker) >= fence_length:
                fence_character = None
                fence_length = 0
            continue
        if fence_character is not None:
            continue
        raw_targets = [match.group(1) for match in LINK_RE.finditer(line)]
        reference_match = REFERENCE_LINK_RE.match(line)
        if reference_match is not None:
            raw_targets.append(reference_match.group(1))
        for raw_target in raw_targets:
            try:
                target = _clean_link_target(raw_target)
                if target is None:
                    continue
                resolved = _resolve_link(path, target)
                if resolved.startswith(INTERNAL_DOC_PREFIXES):
                    raise ValueError("link targets non-public internal documentation")
                if not repository.object_exists(revision, resolved):
                    raise ValueError("link target does not exist in this revision")
            except ValueError as error:
                issues.add(
                    DocsIssue(
                        check_id="PUBLIC-DOC-LINK",
                        path=path,
                        target=raw_target,
                        message=f"line {line_number}: {error}",
                    )
                )
    if fence_character is not None:
        issues.add(
            DocsIssue(
                check_id="PUBLIC-DOC-FENCE",
                path=path,
                target=fence_character * fence_length,
                message="unclosed fenced code block",
            )
        )
    return issues


def revision_docs_issues(
    repository: GitRepository, revision: str
) -> tuple[set[DocsIssue], int]:
    paths = tuple(path for path in repository.list_paths(revision) if is_public_markdown(path))
    issues: set[DocsIssue] = set()
    for path in paths:
        try:
            text = repository.read_text(revision, path)
        except (RuntimeError, UnicodeDecodeError) as error:
            issues.add(
                DocsIssue(
                    check_id="PUBLIC-DOC-UTF8",
                    path=path,
                    target="",
                    message=str(error),
                )
            )
            continue
        issues.update(_document_issues(repository, revision, path, text))
    return issues, len(paths)


def _added_lines(base_text: str, head_text: str) -> tuple[tuple[int, str], ...]:
    """Return only lines introduced or replaced in head, with 1-based numbers."""

    base_lines = base_text.splitlines()
    head_lines = head_text.splitlines()
    matcher = difflib.SequenceMatcher(a=base_lines, b=head_lines, autojunk=False)
    added: list[tuple[int, str]] = []
    for operation, _base_start, _base_end, head_start, head_end in matcher.get_opcodes():
        if operation not in {"insert", "replace"}:
            continue
        added.extend(
            (line_number + 1, head_lines[line_number])
            for line_number in range(head_start, head_end)
        )
    return tuple(added)


def public_evidence_issues(
    repository: GitRepository, classification: Classification
) -> set[DocsIssue]:
    """Reject newly copied provider/run evidence in the two public README files."""

    issues: set[DocsIssue] = set()
    changed_paths = {
        path
        for entry in classification.entries
        for path in entry.paths
        if path in PUBLIC_MARKDOWN_EXACT
    }
    for path in sorted(changed_paths):
        base_text = (
            repository.read_text(classification.base_sha, path)
            if repository.object_exists(classification.base_sha, path)
            else ""
        )
        if not repository.object_exists(classification.head_sha, path):
            continue
        head_text = repository.read_text(classification.head_sha, path)
        for line_number, line in _added_lines(base_text, head_text):
            if not any(pattern.search(line) for pattern in PUBLIC_EVIDENCE_PATTERNS):
                continue
            issues.add(
                DocsIssue(
                    check_id="PUBLIC-DOC-EVIDENCE",
                    path=path,
                    target=line.strip()[:160],
                    message=(
                        f"line {line_number}: public README must not duplicate run, "
                        "artifact, digest, implementation, or closure evidence"
                    ),
                )
            )
    return issues


def validate_public_docs(
    repository: GitRepository, classification: Classification
) -> dict[str, Any]:
    if classification.profile != DOCS_ONLY:
        issue = DocsIssue(
            check_id="PUBLIC-DOC-PROFILE",
            path="",
            target="",
            message="public docs validation requires a proven DOCS_ONLY classification",
        )
        return {
            "schema_version": DOCS_REPORT_VERSION,
            "result": "FAIL",
            "profile": classification.profile,
            "base_sha": classification.base_sha,
            "head_sha": classification.head_sha,
            "checks": [],
            "issues": [asdict(issue)],
        }

    base_issues, base_count = revision_docs_issues(
        repository, classification.base_sha
    )
    head_issues, head_count = revision_docs_issues(
        repository, classification.head_sha
    )
    evidence_issues = public_evidence_issues(repository, classification)
    new_document_issues = head_issues - base_issues
    new_issues = sorted(new_document_issues | evidence_issues)
    result = "PASS" if not new_issues else "FAIL"
    return {
        "schema_version": DOCS_REPORT_VERSION,
        "result": result,
        "profile": classification.profile,
        "base_sha": classification.base_sha,
        "head_sha": classification.head_sha,
        "changed_entries": [asdict(entry) for entry in classification.entries],
        "documents": {"base": base_count, "head": head_count},
        "checks": [
            {
                "check": "no-new-public-document-issues",
                "passed": not new_document_issues,
                "base_issue_count": len(base_issues),
                "head_issue_count": len(head_issues),
                "new_issue_count": len(new_document_issues),
            },
            {
                "check": "no-new-public-provider-evidence",
                "passed": not evidence_issues,
                "new_issue_count": len(evidence_issues),
            },
        ],
        "issues": [asdict(issue) for issue in new_issues],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("classify", "validate-docs"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--base", required=True)
        subparser.add_argument("--head", required=True)
        subparser.add_argument("--report", type=Path, required=True)
        if command == "classify":
            subparser.add_argument("--github-output", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repository = GitRepository(args.root)
    classification = classify_repository(repository, args.base, args.head)
    if args.command == "classify":
        write_json(args.report, _report_payload(classification))
        if args.github_output is not None:
            write_github_output(args.github_output, classification.profile)
        print(f"PASS CI profile: {classification.profile} ({classification.reason})")
        return 0

    payload = validate_public_docs(repository, classification)
    write_json(args.report, payload)
    print(
        f"{payload['result']} public docs validation: "
        f"issues={len(payload['issues'])}"
    )
    return 0 if payload["result"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
