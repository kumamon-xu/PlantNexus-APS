"""Build a bounded, machine-readable context index for one Task Card.

The manifest intentionally contains paths, identities, sizes, and selection reasons;
it never copies document bodies or historical evidence into the report.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any, Sequence, cast


REPORT_VERSION = "task-context-manifest.v1"
DEFAULT_SOFT_CHAR_BUDGET = 30_000
SHA_RE = re.compile(r"(?<![0-9a-fA-F])[0-9a-fA-F]{40}(?![0-9a-fA-F])")
TASK_ID_RE = re.compile(r"TASK-P\d+-\d{2}")
FRONT_MATTER_RE = re.compile(r"\A---\s*\n(?P<body>.*?)\n---\s*\n", re.DOTALL)
BACKTICK_RE = re.compile(r"`([^`]+)`")

CORE_CONTEXT: tuple[tuple[str, str, str], ...] = (
    ("AGENTS.md", "full", "repository entry instructions"),
    ("docs/agents/AGENTS.md", "full", "internal execution entry instructions"),
    ("docs/current_phase.md", "full", "current phase snapshot"),
    (
        "docs/agents/reading-order-and-context-policy.md",
        "exact-sections",
        "context selection policy",
    ),
    (
        "docs/agents/task-execution-protocol.md",
        "exact-sections",
        "task execution protocol",
    ),
)


class GitRepository:
    """Small fail-closed Git adapter used by the context builder."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def run(self, *args: str, check: bool = True) -> str:
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
        return result.stdout

    def head(self) -> str:
        value = self.run("rev-parse", "HEAD").strip().lower()
        if SHA_RE.fullmatch(value) is None:
            raise ValueError("HEAD did not resolve to a full commit SHA")
        return value

    def resolve_commit(self, value: str) -> str:
        if SHA_RE.fullmatch(value) is None:
            raise ValueError(f"invalid full commit SHA: {value!r}")
        resolved = self.run("rev-parse", "--verify", f"{value}^{{commit}}").strip()
        if SHA_RE.fullmatch(resolved) is None:
            raise ValueError(f"commit did not resolve: {value}")
        return resolved.lower()

    def is_ancestor(self, ancestor: str, descendant: str) -> bool:
        result = subprocess.run(
            ["git", "merge-base", "--is-ancestor", ancestor, descendant],
            cwd=self.root,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        return result.returncode == 0

    def changed_paths(self, diff_base: str) -> tuple[str, ...]:
        committed = self.run(
            "diff", "--name-only", "--diff-filter=ACDMRTUXB", f"{diff_base}..HEAD", "--"
        ).splitlines()
        working = self.run(
            "diff", "--name-only", "--diff-filter=ACDMRTUXB", "HEAD", "--"
        ).splitlines()
        untracked = self.run("ls-files", "--others", "--exclude-standard").splitlines()
        return tuple(
            sorted(
                {
                    normalize_repo_path(path)
                    for path in (*committed, *working, *untracked)
                    if path.strip()
                }
            )
        )


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


def parse_front_matter(text: str) -> dict[str, str]:
    match = FRONT_MATTER_RE.match(text)
    if match is None:
        return {}
    result: dict[str, str] = {}
    for line in match.group("body").splitlines():
        key, separator, value = line.partition(":")
        if separator:
            result[key.strip()] = value.strip().strip('"\'')
    return result


def task_field(text: str, name: str) -> str:
    match = re.search(rf"^{re.escape(name)}:\s*(.*?)\s*$", text, re.MULTILINE)
    return match.group(1).strip() if match is not None else ""


def normative_task_text(text: str) -> str:
    return text.split("\n## Activation evidence", 1)[0]


def exact_existing_references(root: Path, task_text: str) -> tuple[str, ...]:
    references: set[str] = set()
    for candidate in BACKTICK_RE.findall(normative_task_text(task_text)):
        if any(character in candidate for character in "*?{}[]"):
            continue
        if any(character.isspace() for character in candidate):
            continue
        if "/" not in candidate and candidate not in {"README.md", "AGENTS.md"}:
            continue
        try:
            path = normalize_repo_path(candidate)
        except ValueError:
            continue
        if (root / path).is_file():
            references.add(path)
    return tuple(sorted(references))


def find_task_card(root: Path, task_id: str) -> Path | None:
    matches = sorted((root / "docs" / "tasks").glob(f"*/{task_id}-*.md"))
    if len(matches) > 1:
        raise ValueError(f"multiple Task Cards found for {task_id}")
    return matches[0] if matches else None


def evidence_identities(text: str) -> tuple[str, ...]:
    identities: set[str] = set()
    for line in text.splitlines():
        lowered = line.lower()
        if "implementation" not in lowered and "closure" not in lowered:
            continue
        identities.update(value.lower() for value in SHA_RE.findall(line))
    return tuple(sorted(identities))


def dependency_records(
    root: Path,
    repository: GitRepository,
    dependency_field: str,
    head_sha: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    records: list[dict[str, Any]] = []
    issues: list[str] = []
    for task_id in sorted(set(TASK_ID_RE.findall(dependency_field))):
        card = find_task_card(root, task_id)
        if card is None:
            issues.append(f"direct dependency has no Task Card: {task_id}")
            continue
        text = card.read_text(encoding="utf-8")
        metadata = parse_front_matter(text)
        status = metadata.get("status", "")
        identities = evidence_identities(text)
        identity_checks: list[dict[str, object]] = []
        if status != "done":
            issues.append(f"direct dependency is not done: {task_id}={status or 'unknown'}")
        for identity in identities:
            try:
                resolved = repository.resolve_commit(identity)
                ancestor = repository.is_ancestor(resolved, head_sha)
            except (RuntimeError, ValueError) as error:
                resolved = identity
                ancestor = False
                issues.append(f"invalid dependency identity {task_id}/{identity}: {error}")
            if not ancestor:
                issues.append(
                    f"dependency identity is not an ancestor of HEAD: {task_id}/{identity}"
                )
            identity_checks.append({"sha": resolved, "ancestor_of_head": ancestor})
        records.append(
            {
                "task_id": task_id,
                "status": status,
                "path": card.relative_to(root).as_posix(),
                "evidence_identities": identity_checks,
            }
        )
    return records, issues


def add_selection(
    selected: dict[str, dict[str, object]],
    root: Path,
    path: str,
    load_mode: str,
    reason: str,
    issues: list[str],
) -> None:
    try:
        normalized = normalize_repo_path(path)
    except ValueError as error:
        issues.append(str(error))
        return
    absolute = root / normalized
    if not absolute.is_file():
        issues.append(f"required context file does not exist: {normalized}")
        return
    try:
        characters = len(absolute.read_text(encoding="utf-8"))
    except UnicodeDecodeError:
        issues.append(f"required context file is not UTF-8: {normalized}")
        return
    planned_characters = {
        "full": characters,
        "exact-sections": min(characters, 4_000),
        "completion-summary-only": min(characters, 2_000),
        "reference-only": 0,
        "affected-file": 0,
    }.get(load_mode, 0)
    existing = selected.get(normalized)
    if existing is None:
        selected[normalized] = {
            "path": normalized,
            "load_mode": load_mode,
            "reason": reason,
            "characters": characters,
            "planned_characters": planned_characters,
        }
    else:
        existing["reason"] = f"{existing['reason']}; {reason}"
        priority = {
            "reference-only": 1,
            "affected-file": 2,
            "completion-summary-only": 3,
            "exact-sections": 4,
            "full": 5,
        }
        existing_mode = str(existing["load_mode"])
        if priority.get(load_mode, 0) > priority.get(existing_mode, 0):
            existing["load_mode"] = load_mode
            existing["planned_characters"] = planned_characters


def expansion_triggers(paths: Sequence[str]) -> list[dict[str, object]]:
    groups = {
        "ci-and-provider": (
            ".github/workflows/",
            "scripts/ci_",
            "scripts/provider_evidence.py",
        ),
        "schema-and-migration": ("schemas/", "backend/migrations/"),
        "dependencies": ("pyproject.toml", "uv.lock", "package.json", "package-lock.json"),
        "frontend-browser": ("frontend/",),
    }
    result: list[dict[str, object]] = []
    for name, prefixes in groups.items():
        matched = sorted(
            path
            for path in paths
            if any(path == prefix or path.startswith(prefix) for prefix in prefixes)
        )
        result.append({"trigger": name, "active": bool(matched), "matched_paths": matched})
    return result


def build_manifest(
    root: Path,
    task_path: Path,
    *,
    soft_char_budget: int = DEFAULT_SOFT_CHAR_BUDGET,
) -> dict[str, Any]:
    root = root.resolve()
    task_path = task_path.resolve()
    issues: list[str] = []
    warnings: list[str] = []
    if soft_char_budget <= 0:
        raise ValueError("soft character budget must be positive")
    if not task_path.is_relative_to(root) or not task_path.is_file():
        raise ValueError("Task Card must be an existing file inside the repository")

    repository = GitRepository(root)
    head_sha = repository.head()
    task_text = task_path.read_text(encoding="utf-8")
    metadata = parse_front_matter(task_text)
    task_id = metadata.get("doc_id", "")
    if TASK_ID_RE.fullmatch(task_id) is None:
        issues.append(f"Task Card has invalid doc_id: {task_id!r}")
    if metadata.get("status") not in {"ready", "in_progress"}:
        issues.append(
            "context manifest requires a ready or in_progress Task Card; "
            f"found {metadata.get('status', 'unknown')!r}"
        )

    diff_base_value = task_field(task_text, "Diff base")
    try:
        diff_base = repository.resolve_commit(diff_base_value)
    except (RuntimeError, ValueError) as error:
        diff_base = diff_base_value
        issues.append(f"invalid Diff base: {error}")

    dependency_items, dependency_issues = dependency_records(
        root,
        repository,
        task_field(task_text, "Depends on"),
        head_sha,
    )
    issues.extend(dependency_issues)
    changed_paths = repository.changed_paths(diff_base) if SHA_RE.fullmatch(diff_base) else ()

    selected: dict[str, dict[str, object]] = {}
    for path, mode, reason in CORE_CONTEXT:
        add_selection(selected, root, path, mode, reason, issues)
    task_relative = task_path.relative_to(root).as_posix()
    add_selection(selected, root, task_relative, "full", "active Task Card", issues)

    validation_profile = task_field(task_text, "Validation profile")
    task_scope_text = normative_task_text(task_text)
    if validation_profile == "HIGH_RISK":
        add_selection(
            selected,
            root,
            "docs/quality/ci-gates-and-definition-of-done.md",
            "exact-sections",
            "HIGH_RISK validation profile",
            issues,
        )
    if ".github/workflows/" in task_scope_text or "scripts/ci_" in task_scope_text:
        add_selection(
            selected,
            root,
            "docs/quality/documentation-consistency-checks.md",
            "exact-sections",
            "CI/governance validator scope",
            issues,
        )
        add_selection(
            selected,
            root,
            "docs/architecture/configuration-environments-and-isolation.md",
            "exact-sections",
            "CI infrastructure documentation impact",
            issues,
        )
    for dependency in dependency_items:
        add_selection(
            selected,
            root,
            str(dependency["path"]),
            "completion-summary-only",
            "direct dependency identity and status",
            issues,
        )
    for path in exact_existing_references(root, task_text):
        add_selection(selected, root, path, "reference-only", "exact Task reference", issues)
    for path in changed_paths:
        if (root / path).is_file():
            add_selection(selected, root, path, "affected-file", "current Task diff", issues)

    selection = [selected[path] for path in sorted(selected)]
    indexed_characters = sum(cast(int, item["characters"]) for item in selection)
    estimated_characters = sum(
        cast(int, item["planned_characters"]) for item in selection
    )
    over_budget = estimated_characters > soft_char_budget
    if over_budget:
        warnings.append(
            "selected context exceeds the soft budget; use the declared load modes and "
            "expand exact sections instead of silently truncating"
        )

    return {
        "schema_version": REPORT_VERSION,
        "result": "PASS" if not issues else "FAIL",
        "task": {
            "task_id": task_id,
            "status": metadata.get("status", ""),
            "phase": metadata.get("phase", ""),
            "path": task_relative,
            "validation_profile": validation_profile,
        },
        "git": {
            "head_sha": head_sha,
            "diff_base": diff_base,
            "changed_paths": list(changed_paths),
        },
        "dependencies": dependency_items,
        "selection": selection,
        "budget": {
            "kind": "soft-character-budget",
            "limit": soft_char_budget,
            "estimated_selected_characters": estimated_characters,
            "indexed_file_characters": indexed_characters,
            "over_budget": over_budget,
            "behavior": "warn-and-expand-exact-sections; never truncate silently",
        },
        "expansion_triggers": expansion_triggers(changed_paths),
        "warnings": warnings,
        "issues": issues,
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
    parser.add_argument("--task", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument(
        "--soft-char-budget", type=int, default=DEFAULT_SOFT_CHAR_BUDGET
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root.resolve()
    task_path = args.task if args.task.is_absolute() else root / args.task
    report_path = args.report if args.report.is_absolute() else root / args.report
    try:
        report = build_manifest(
            root,
            task_path,
            soft_char_budget=args.soft_char_budget,
        )
        write_report(report_path, root, report)
    except (OSError, RuntimeError, ValueError) as error:
        print(f"FAIL task context manifest: {error}", file=sys.stderr)
        return 1
    print(
        f"{report['result']} task context manifest: "
        f"task={report['task']['task_id']} files={len(report['selection'])} "
        f"characters={report['budget']['estimated_selected_characters']} "
        f"issues={len(report['issues'])}"
    )
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
