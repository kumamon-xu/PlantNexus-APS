"""Validate PlantNexus APS documentation and governance traceability.

TASK-P0-01 established structural Markdown checks. TASK-P0-02 extends the
same dependency-free command with versioned registry, reference, Task Card,
traceability, and Git diff/change-impact validation.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Mapping, Sequence, cast
from urllib.parse import unquote


REPORT_SCHEMA_VERSION = "traceability-report.v1"
REGISTRY_FORMAT_VERSION = "1.0.0"

REQUIRED_METADATA = {
    "doc_id",
    "title",
    "status",
    "spec_version",
    "phase",
    "normative",
    "source_sections",
    "last_reviewed",
}
REQUIRED_TASK_FIELDS = (
    "Requirement IDs",
    "NFR / ENG IDs",
    "Depends on",
    "Goal",
    "Inputs",
    "Files allowed to change",
    "Files forbidden to change",
    "Implementation steps",
    "Outputs",
    "Documentation impact",
    "Documents to update",
    "Documentation impact rationale",
    "Change-impact matrix rows reviewed",
    "Traceability updates",
    "Schema changes",
    "Migration",
    "Error behavior",
    "Tests",
    "Benchmark impact",
    "Simulation scenarios",
    "Acceptance commands",
    "Artifacts",
    "Explicitly excluded",
    "PROD_OPEN",
    "SIM_ASSUMPTIONS",
    "Rollback",
)
TASK_STATUSES = {"planned", "ready", "in_progress", "blocked", "done", "cancelled"}
TERMINAL_TASK_STATUSES = {"done", "cancelled"}
P1_REQUIRED_TASK_FIELDS = ("Completion conditions",)
P2_REQUIRED_TASK_FIELDS = (
    "Start gate",
    "Dependency changes",
    "ADR impact",
    "Provider evidence",
)
PHASE_PLANNING_OWNER_ROLE = "phase-planning-owner"
PHASE_PLAN_AMENDMENT_OWNER_ROLE = "phase-plan-amendment-owner"
PHASE_PLAN_MEMBER_ROLE = "phase-plan-member"

VERSIONED_REGISTRIES = (
    "docs/governance/requirements-register.md",
    "docs/governance/nfr-and-engineering-register.md",
    "docs/governance/traceability-matrix.md",
    "docs/governance/prod-open-register.md",
    "docs/governance/sim-assumption-register.md",
    "docs/governance/risk-register.md",
    "docs/governance/change-impact-matrix.md",
    "docs/governance/document-inventory.md",
    "docs/quality/test-strategy-and-matrix.md",
)

CHECK_DESCRIPTIONS = {
    "DOC-METADATA": "formal Markdown metadata and spec version",
    "DOC-ID-UNIQUE": "unique document IDs",
    "DOC-FENCE": "balanced Markdown fences",
    "DOC-LINK": "existing local Markdown links",
    "DOC-INVENTORY": "document inventory coverage and metadata",
    "REGISTRY-VERSION": "governance registry format versions",
    "REGISTRY-PARSE": "machine-readable registry tables",
    "REGISTRY-ID-UNIQUE": "registry ID format and definition uniqueness",
    "REFERENCE-VALID": "registered ID references",
    "TRACE-COVERAGE": "one traceability row per root ID",
    "TRACE-PATH": "real normative and artifact paths",
    "TASK-FIELDS": "required Task Card fields",
    "TASK-REFERENCES": "Task requirement, dependency, and document references",
    "TASK-DEPENDENCY": "active/completed Task dependencies",
    "TASK-SCOPE": "actual diff remains inside current Task scope",
    "PHASE-TASK": "only current-phase detailed Task Cards",
    "PROD-SIM-SEPARATION": "PROD_OPEN and SIM_ASSUMPTION separation",
    "PROD-CLOSURE": "complete PROD_OPEN closure evidence",
    "DIFF-IMPACT": "Git diff/change-impact coverage",
}

FRONT_MATTER_RE = re.compile(r"\A---\s*\n(?P<body>.*?)\n---\s*\n", re.DOTALL)
LINK_RE = re.compile(r"!?\[[^\]]*\]\((?P<target>[^)]+)\)")
FENCE_RE = re.compile(r"^\s*(```|~~~)")
BACKTICK_RE = re.compile(r"`([^`]+)`")

ROOT_ID_RE = re.compile(
    r"(?<![A-Z0-9_-])(?:REQ-\d{3}|NFR-[A-Z]+-\d{3}|ENG-[A-Z]+-\d{3})(?![A-Z0-9_-])"
)
TEST_ID_RE = re.compile(r"(?<![A-Z0-9_-])TEST-[A-Z0-9]+(?:-[A-Z0-9]+)*(?![A-Z0-9_-])")
TASK_ID_RE = re.compile(r"(?<![A-Z0-9_-])TASK-P\d+-\d{2}(?![A-Z0-9_-])")
PHASE_ID_RE = re.compile(r"P(?P<number>\d+)")
TASK_CARD_PATH_RE = re.compile(
    r"^docs/tasks/(?P<folder_phase>P\d+)/"
    r"TASK-(?P<id_phase>P\d+)-(?P<number>\d{2})-[^/]+\.md$"
)
CONSTRAINT_ID_RE = re.compile(r"(?<![A-Z0-9_-])C-\d{3}(?![A-Z0-9_-])")
OBJECTIVE_ID_RE = re.compile(r"(?<![A-Z0-9_-])OBJ-\d{3}(?![A-Z0-9_-])")
ADR_ID_RE = re.compile(r"(?<![A-Z0-9_-])ADR-\d{4}(?![A-Z0-9_-])")
OPEN_ID_RE = re.compile(r"(?<![A-Z0-9_-])OPEN-\d{3}(?![A-Z0-9_-])")
SIM_ID_RE = re.compile(
    r"(?<![A-Z0-9_-])SIM(?:-|_)ASSUMPTION-\d{3}(?![A-Z0-9_-])"
)
RISK_ID_RE = re.compile(r"(?<![A-Z0-9_-])RISK-\d{3}(?![A-Z0-9_-])")
IMPACT_ID_RE = re.compile(r"(?<![A-Z0-9_-])IMPACT-[A-Z0-9]+(?:-[A-Z0-9]+)*(?![A-Z0-9_-])")
COMMIT_SHA_RE = re.compile(r"[0-9a-fA-F]{40}")


@dataclass(frozen=True)
class Issue:
    """One actionable validation failure."""

    check_id: str
    severity: str
    path: str
    message: str
    suggestion: str


@dataclass(frozen=True)
class ImpactRule:
    """One machine-readable path-to-document impact rule."""

    rule_id: str
    patterns: tuple[str, ...]
    required_docs: tuple[str, ...]


@dataclass(frozen=True)
class ImpactCoverage:
    """Result of matching a changed-path set to impact rules."""

    matched_rule_ids: tuple[str, ...]
    expected_docs: tuple[str, ...]
    issues: tuple[Issue, ...]


class TaskDiscoveryError(ValueError):
    """A CI change range cannot be attributed to one current-phase Task."""


def normalize_repo_path(value: str) -> str:
    """Normalize a repository path from Markdown or Git output."""

    normalized = value.strip().strip("<>").replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized.lstrip("/")


def parse_front_matter(text: str) -> dict[str, str]:
    """Parse the simple top-level YAML scalars used by repository documents."""

    match = FRONT_MATTER_RE.match(text)
    if match is None:
        return {}
    metadata: dict[str, str] = {}
    for line in match.group("body").splitlines():
        if not line or line[0].isspace() or ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip()
    return metadata


def split_markdown_row(line: str) -> list[str]:
    """Split a simple Markdown table row into stripped cells."""

    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def parse_markdown_tables(text: str) -> list[list[dict[str, str]]]:
    """Parse simple pipe tables without interpreting inline Markdown."""

    lines = text.splitlines()
    tables: list[list[dict[str, str]]] = []
    index = 0
    while index + 1 < len(lines):
        header_line = lines[index]
        separator_line = lines[index + 1]
        if not header_line.lstrip().startswith("|") or not separator_line.lstrip().startswith("|"):
            index += 1
            continue
        headers = split_markdown_row(header_line)
        separators = split_markdown_row(separator_line)
        if len(headers) != len(separators) or not all(
            re.fullmatch(r":?-{3,}:?", cell) for cell in separators
        ):
            index += 1
            continue

        rows: list[dict[str, str]] = []
        index += 2
        while index < len(lines) and lines[index].lstrip().startswith("|"):
            cells = split_markdown_row(lines[index])
            if len(cells) == len(headers):
                rows.append(dict(zip(headers, cells, strict=True)))
            index += 1
        tables.append(rows)
    return tables


def find_table(text: str, required_headers: set[str]) -> list[dict[str, str]] | None:
    """Find the first Markdown table containing all required headers."""

    for rows in parse_markdown_tables(text):
        if rows and required_headers.issubset(rows[0]):
            return rows
    return None


def extract_backtick_values(text: str) -> list[str]:
    """Extract inline-code values in source order."""

    return [match.group(1).strip() for match in BACKTICK_RE.finditer(text)]


def extract_task_field(text: str, field: str) -> str:
    """Read one single-line Task Card field."""

    match = re.search(rf"^{re.escape(field)}:\s*(.*?)\s*$", text, re.MULTILINE)
    return match.group(1).strip() if match else ""


def missing_task_fields(text: str) -> list[str]:
    """Return required Task fields that are absent or empty."""

    return [field for field in REQUIRED_TASK_FIELDS if not extract_task_field(text, field)]


def duplicate_id_issues(
    entries: Iterable[tuple[str, str]],
    *,
    check_id: str = "REGISTRY-ID-UNIQUE",
) -> list[Issue]:
    """Return issues for IDs defined more than once."""

    issues: list[Issue] = []
    seen: dict[str, str] = {}
    for identifier, path in entries:
        previous = seen.get(identifier)
        if previous is not None:
            issues.append(
                Issue(
                    check_id,
                    "error",
                    path,
                    f"duplicate definition {identifier!r}; first defined in {previous}",
                    "keep one canonical registry row and preserve retired IDs instead of reusing them",
                )
            )
        else:
            seen[identifier] = path
    return issues


def unknown_reference_issues(
    documents: Mapping[str, str],
    known_ids: set[str],
    pattern: re.Pattern[str],
    *,
    normalize: Callable[[str], str] | None = None,
) -> list[Issue]:
    """Return one issue per path/unknown-ID pair."""

    issues: list[Issue] = []
    observed: set[tuple[str, str]] = set()
    for path, text in documents.items():
        for match in pattern.finditer(text):
            raw_identifier = match.group(0)
            identifier = normalize(raw_identifier) if normalize else raw_identifier
            key = (path, raw_identifier)
            if identifier not in known_ids and key not in observed:
                observed.add(key)
                issues.append(
                    Issue(
                        "REFERENCE-VALID",
                        "error",
                        path,
                        f"reference {raw_identifier!r} has no registered definition",
                        "register the ID in its canonical registry or correct the reference",
                    )
                )
    return issues


def namespace_separation_issues(prod_text: str, sim_text: str) -> list[Issue]:
    """Reject concrete cross-namespace IDs in the two authority registries."""

    issues: list[Issue] = []
    sim_in_prod = sorted(set(SIM_ID_RE.findall(prod_text)))
    open_in_sim = sorted(set(OPEN_ID_RE.findall(sim_text)))
    if sim_in_prod:
        issues.append(
            Issue(
                "PROD-SIM-SEPARATION",
                "error",
                "docs/governance/prod-open-register.md",
                f"simulation IDs appear in PROD_OPEN registry: {', '.join(sim_in_prod)}",
                "move simulation assumptions to sim-assumption-register.md",
            )
        )
    if open_in_sim:
        issues.append(
            Issue(
                "PROD-SIM-SEPARATION",
                "error",
                "docs/governance/sim-assumption-register.md",
                f"production-open IDs appear in SIM_ASSUMPTION registry: {', '.join(open_in_sim)}",
                "reference production questions outside the simulation registry table/contract",
            )
        )
    return issues


def evaluate_impact_coverage(
    changed_paths: Sequence[str],
    rules: Sequence[ImpactRule],
    declared_rule_ids: set[str],
    declared_docs: set[str],
) -> ImpactCoverage:
    """Match actual changed paths and validate Task impact declarations."""

    matched: set[str] = set()
    expected_docs: set[str] = set()
    issues: list[Issue] = []
    rule_by_id = {rule.rule_id: rule for rule in rules}

    for changed_path in changed_paths:
        if changed_path.endswith("/.gitkeep") or changed_path == ".gitkeep":
            continue
        path_matches = [
            rule
            for rule in rules
            if any(fnmatch.fnmatchcase(changed_path, pattern) for pattern in rule.patterns)
        ]
        if not path_matches:
            issues.append(
                Issue(
                    "DIFF-IMPACT",
                    "error",
                    changed_path,
                    "changed path does not match any machine-readable impact rule",
                    "add a bounded change-impact rule before continuing the Task",
                )
            )
        for rule in path_matches:
            matched.add(rule.rule_id)
            expected_docs.update(rule.required_docs)

    for rule_id in sorted(matched - declared_rule_ids):
        issues.append(
            Issue(
                "DIFF-IMPACT",
                "error",
                "Task Card",
                f"matched impact rule {rule_id} is missing from Change-impact matrix rows reviewed",
                "add the Rule ID to the Task Card before implementation",
            )
        )
    for rule_id in sorted(declared_rule_ids - matched):
        if rule_id in rule_by_id:
            issues.append(
                Issue(
                    "DIFF-IMPACT",
                    "error",
                    "Task Card",
                    f"declared impact rule {rule_id} does not match the actual Git diff",
                    "remove the stale Rule ID or include the intended bounded change",
                )
            )
    for document in sorted(expected_docs - declared_docs):
        issues.append(
            Issue(
                "DIFF-IMPACT",
                "error",
                "Task Card",
                f"required review document {document!r} is absent from Documents to update",
                "add the exact path to Documents to update and Files allowed to change",
            )
        )

    return ImpactCoverage(tuple(sorted(matched)), tuple(sorted(expected_docs)), tuple(issues))


def expand_numeric_ranges(text: str, prefix: str, digits: int) -> set[str]:
    """Extract exact IDs and expand full or shortened ideographic-tilde ranges."""

    escaped = re.escape(prefix)
    exact_re = re.compile(rf"(?<![A-Z0-9_-]){escaped}\d{{{digits}}}(?![A-Z0-9_-])")
    range_re = re.compile(
        rf"{escaped}(?P<start>\d{{{digits}}})\s*～\s*(?:{escaped})?(?P<end>\d{{{digits}}})"
    )
    identifiers = set(exact_re.findall(text))
    for match in range_re.finditer(text):
        start = int(match.group("start"))
        end = int(match.group("end"))
        if start <= end:
            identifiers.update(f"{prefix}{value:0{digits}d}" for value in range(start, end + 1))
    return identifiers


def expand_task_ranges(text: str) -> set[str]:
    """Extract Task IDs and expand ranges within one numbered phase."""

    identifiers = set(TASK_ID_RE.findall(text))
    range_re = re.compile(
        r"TASK-P(?P<phase>\d+)-(?P<start>\d{2})\s*～\s*"
        r"(?:TASK-P(?P<end_phase>\d+)-)?(?P<end>\d{2})"
    )
    for match in range_re.finditer(text):
        phase = match.group("phase")
        end_phase = match.group("end_phase")
        if end_phase is not None and end_phase != phase:
            continue
        start = int(match.group("start"))
        end = int(match.group("end"))
        if start <= end:
            identifiers.update(
                f"TASK-P{phase}-{value:02d}" for value in range(start, end + 1)
            )
    return identifiers


def phase_number(value: str) -> int | None:
    """Return the numeric phase for an exact Pn identifier."""

    match = PHASE_ID_RE.fullmatch(value)
    return int(match.group("number")) if match is not None else None


def task_phase_policy_issue(
    task_id: str,
    folder_phase: str,
    metadata_phase: str,
    current_phase: str,
    status: str,
) -> tuple[str, str] | None:
    """Return one phase-policy failure for a Task Card, if any."""

    task_match = re.fullmatch(r"TASK-(P\d+)-\d{2}", task_id)
    task_phase = task_match.group(1) if task_match is not None else ""
    task_phase_number = phase_number(task_phase)
    current_phase_number = phase_number(current_phase)
    if not (
        task_phase
        and folder_phase == task_phase
        and metadata_phase == task_phase
        and task_phase_number is not None
    ):
        return (
            "Task ID, directory, and phase metadata do not identify the same phase",
            "align TASK-Pn-NN, docs/tasks/Pn, and front matter phase",
        )
    if current_phase_number is None:
        return None
    if task_phase_number > current_phase_number:
        return (
            f"detailed Task Card belongs to future {task_phase}, current phase is {current_phase}",
            "keep future phases at Milestone level until explicitly authorized",
        )
    if task_phase_number < current_phase_number and status not in TERMINAL_TASK_STATUSES:
        return (
            f"historical {task_phase} Task remains non-terminal in current {current_phase}",
            "finish or cancel prior-phase Tasks before advancing the phase",
        )
    return None


def select_changed_task_path(
    changed_paths: Iterable[str],
    current_phase: str,
    *,
    added_paths: Iterable[str] = (),
    task_texts: Mapping[str, str] | None = None,
    base_task_texts: Mapping[str, str] | None = None,
) -> str | None:
    """Select the one current-phase Task Card changed by a CI event range."""

    if phase_number(current_phase) is None:
        raise TaskDiscoveryError(f"current phase {current_phase!r} is not an exact Pn value")

    candidates: set[str] = set()
    noncurrent: set[str] = set()
    misaligned: set[str] = set()
    for raw_path in changed_paths:
        path = normalize_repo_path(raw_path)
        match = TASK_CARD_PATH_RE.fullmatch(path)
        if match is None:
            continue
        folder_phase = match.group("folder_phase")
        id_phase = match.group("id_phase")
        if folder_phase != id_phase:
            misaligned.add(path)
        elif folder_phase == current_phase:
            candidates.add(path)
        else:
            noncurrent.add(path)

    if misaligned:
        raise TaskDiscoveryError(
            "changed Task path has mismatched directory/ID phase: "
            + ", ".join(sorted(misaligned))
        )
    if noncurrent:
        raise TaskDiscoveryError(
            f"change range modifies Task Cards outside current {current_phase}: "
            + ", ".join(sorted(noncurrent))
        )
    if not candidates:
        return None

    logical_paths: dict[str, set[str]] = {}
    for candidate in candidates:
        match = TASK_CARD_PATH_RE.fullmatch(candidate)
        assert match is not None
        task_id = f"TASK-{match.group('id_phase')}-{match.group('number')}"
        logical_paths.setdefault(task_id, set()).add(candidate)

    if len(logical_paths) == 1:
        if task_texts is None:
            if len(candidates) == 1:
                return next(iter(candidates))
            raise TaskDiscoveryError(
                "change range contains multiple paths for one logical Task Card: "
                + ", ".join(sorted(candidates))
            )
        surviving = sorted(path for path in candidates if path in task_texts)
        if len(surviving) == 1:
            return surviving[0]
        if not surviving:
            raise TaskDiscoveryError("change range deletes the selected logical Task Card")
        raise TaskDiscoveryError(
            "change range leaves multiple paths for one logical Task Card: "
            + ", ".join(surviving)
        )

    if task_texts is None:
        raise TaskDiscoveryError(
            f"change range contains multiple current {current_phase} Task Cards: "
            + ", ".join(sorted(candidates))
        )

    surviving_by_id: dict[str, str] = {}
    for task_id, paths in sorted(logical_paths.items()):
        surviving = sorted(path for path in paths if path in task_texts)
        if not surviving:
            raise TaskDiscoveryError(
                f"phase-plan batch may not delete logical Task Cards: {task_id}"
            )
        if len(surviving) > 1:
            raise TaskDiscoveryError(
                f"phase-plan batch leaves multiple paths for {task_id}: "
                + ", ".join(surviving)
            )
        surviving_by_id[task_id] = surviving[0]

    normalized_added = {normalize_repo_path(path) for path in added_paths}
    if candidates.issubset(normalized_added):
        owners: list[str] = []
        for task_id, candidate in sorted(surviving_by_id.items()):
            text = task_texts[candidate]
            metadata = parse_front_matter(text)
            if extract_task_field(text, "Task batch role") != PHASE_PLANNING_OWNER_ROLE:
                continue
            expected_owner = f"TASK-{current_phase}-00"
            if task_id != expected_owner or metadata.get("doc_id") != expected_owner:
                raise TaskDiscoveryError(
                    "phase-planning owner must be the current phase TASK-Pn-00 card"
                )
            if metadata.get("status") not in {"in_progress", "done"}:
                raise TaskDiscoveryError(
                    "phase-planning owner must be in_progress or done"
                )
            if COMMIT_SHA_RE.fullmatch(extract_task_field(text, "Diff base")) is None:
                raise TaskDiscoveryError(
                    "phase-planning owner must have a full immutable Diff base"
                )
            owners.append(candidate)

        if len(owners) != 1:
            raise TaskDiscoveryError(
                "multiple-card change range requires exactly one TASK-Pn-00 "
                f"{PHASE_PLANNING_OWNER_ROLE!r}; found {len(owners)}"
            )

        owner = owners[0]
        for candidate in sorted(set(surviving_by_id.values()) - {owner}):
            text = task_texts[candidate]
            metadata = parse_front_matter(text)
            if extract_task_field(text, "Task batch role") != PHASE_PLAN_MEMBER_ROLE:
                raise TaskDiscoveryError(
                    f"phase-plan member lacks role {PHASE_PLAN_MEMBER_ROLE!r}: {candidate}"
                )
            if metadata.get("status") not in {"planned", "ready"}:
                raise TaskDiscoveryError(
                    f"phase-plan member must remain planned or ready: {candidate}"
                )
            if COMMIT_SHA_RE.fullmatch(extract_task_field(text, "Diff base")) is not None:
                raise TaskDiscoveryError(
                    f"phase-plan member must not pre-allocate an implementation Diff base: {candidate}"
                )
        return owner

    if any(
        extract_task_field(task_texts[candidate], "Task batch role")
        == PHASE_PLANNING_OWNER_ROLE
        for candidate in surviving_by_id.values()
    ):
        existing = sorted(candidates - normalized_added)
        raise TaskDiscoveryError(
            "phase-planning batch may contain only newly added Task Cards; "
            f"existing cards changed: {', '.join(existing)}"
        )

    amendment_owners: list[tuple[str, str]] = []
    for task_id, candidate in sorted(surviving_by_id.items()):
        text = task_texts[candidate]
        metadata = parse_front_matter(text)
        if extract_task_field(text, "Task batch role") != PHASE_PLAN_AMENDMENT_OWNER_ROLE:
            continue
        if metadata.get("doc_id") != task_id:
            raise TaskDiscoveryError(
                "phase-plan amendment owner path and doc_id must identify the same Task"
            )
        if metadata.get("status") not in {"in_progress", "done"}:
            raise TaskDiscoveryError(
                "phase-plan amendment owner must be in_progress or done"
            )
        if COMMIT_SHA_RE.fullmatch(extract_task_field(text, "Diff base")) is None:
            raise TaskDiscoveryError(
                "phase-plan amendment owner must have a full immutable Diff base"
            )
        amendment_owners.append((task_id, candidate))

    if len(amendment_owners) != 1:
        raise TaskDiscoveryError(
            "phase-plan amendment requires exactly one "
            f"{PHASE_PLAN_AMENDMENT_OWNER_ROLE!r}; found {len(amendment_owners)}"
        )

    owner_task_id, owner = amendment_owners[0]
    base_status_by_id: dict[str, str] = {}
    for path, text in (base_task_texts or {}).items():
        match = TASK_CARD_PATH_RE.fullmatch(normalize_repo_path(path))
        if match is None:
            continue
        task_id = f"TASK-{match.group('id_phase')}-{match.group('number')}"
        base_status_by_id[task_id] = parse_front_matter(text).get("status", "")

    if owner_task_id not in base_status_by_id:
        raise TaskDiscoveryError(
            "phase-plan amendment owner must already exist at the event base"
        )

    for task_id, candidate in sorted(surviving_by_id.items()):
        if task_id == owner_task_id:
            continue
        text = task_texts[candidate]
        metadata = parse_front_matter(text)
        if base_status_by_id.get(task_id) in {"in_progress", "done"}:
            raise TaskDiscoveryError(
                f"phase-plan amendment may not modify active or completed member: {task_id}"
            )
        if extract_task_field(text, "Task batch role") != PHASE_PLAN_MEMBER_ROLE:
            raise TaskDiscoveryError(
                f"phase-plan amendment member lacks role {PHASE_PLAN_MEMBER_ROLE!r}: {candidate}"
            )
        if metadata.get("status") not in {"planned", "ready"}:
            raise TaskDiscoveryError(
                f"phase-plan amendment member must remain planned or ready: {candidate}"
            )
        if COMMIT_SHA_RE.fullmatch(extract_task_field(text, "Diff base")) is not None:
            raise TaskDiscoveryError(
                "phase-plan amendment member must not pre-allocate an implementation "
                f"Diff base: {candidate}"
            )
    return owner


def local_link_target(source: Path, raw_target: str) -> Path | None:
    """Resolve a local Markdown link, ignoring URLs and same-page anchors."""

    target = raw_target.strip()
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1]
    target = unquote(target.split("#", 1)[0].strip())
    if not target or re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target):
        return None
    return (source.parent / target).resolve()


class RepositoryValidator:
    """Run structural and traceability validation against one repository root."""

    def __init__(
        self,
        repository_root: Path,
        task_path: Path | None = None,
        task_discovery_base: str | None = None,
    ) -> None:
        self.root = repository_root.resolve()
        self.docs_root = self.root / "docs"
        self.source_spec = self.docs_root / "core" / "APS_IMPLEMENTATION_SPEC.md"
        self.inventory = self.docs_root / "governance" / "document-inventory.md"
        self.task_path = task_path.resolve() if task_path else None
        self.task_discovery_base = task_discovery_base

        self.issues: list[Issue] = []
        self.executed_checks: set[str] = set()
        self.doc_texts: dict[str, str] = {}
        self.metadata: dict[str, dict[str, str]] = {}
        self.task_records: dict[str, dict[str, object]] = {}
        self.impact_rules: list[ImpactRule] = []
        self.changed_paths: list[str] = []
        self.matched_impact_rows: list[str] = []
        self.expected_docs: list[str] = []
        self.observed_docs: list[str] = []
        self.diff_base: str | None = None
        self.diff_source_counts: dict[str, int] = {}
        self.current_phase: str | None = None
        self.missing_trace_refs: set[str] = set()
        self.counts: dict[str, int] = {}

        self.root_ids: set[str] = set()
        self.test_ids: set[str] = set()
        self.task_ids: set[str] = set()
        self.constraint_ids: set[str] = set()
        self.objective_ids: set[str] = set()
        self.adr_ids: set[str] = set()
        self.open_ids: set[str] = set()
        self.sim_ids: set[str] = set()
        self.risk_ids: set[str] = set()

    def relative(self, path: Path) -> str:
        """Return a stable repository-relative path for diagnostics."""

        try:
            return path.resolve().relative_to(self.root).as_posix()
        except ValueError:
            return str(path)

    def mark(self, *check_ids: str) -> None:
        self.executed_checks.update(check_ids)

    def add_issue(
        self,
        check_id: str,
        path: str,
        message: str,
        suggestion: str,
    ) -> None:
        self.mark(check_id)
        self.issues.append(Issue(check_id, "error", path, message, suggestion))

    def absorb(self, issues: Iterable[Issue]) -> None:
        for issue in issues:
            self.mark(issue.check_id)
            self.issues.append(issue)
            if issue.check_id == "REFERENCE-VALID":
                self.missing_trace_refs.add(f"{issue.path}: {issue.message}")

    def validate_fences(self, path: Path, text: str) -> None:
        self.mark("DOC-FENCE")
        active: str | None = None
        for line_number, line in enumerate(text.splitlines(), start=1):
            match = FENCE_RE.match(line)
            if match is None:
                continue
            marker = match.group(1)
            if active is None:
                active = marker
            elif marker == active:
                active = None
            else:
                self.add_issue(
                    "DOC-FENCE",
                    f"{self.relative(path)}:{line_number}",
                    f"fence {marker!r} closes {active!r}",
                    "close the active fence with the same marker",
                )
        if active is not None:
            self.add_issue(
                "DOC-FENCE",
                self.relative(path),
                f"unclosed {active!r} fence",
                "add the matching closing fence",
            )

    def validate_links(self, path: Path, text: str) -> int:
        self.mark("DOC-LINK")
        checked = 0
        for match in LINK_RE.finditer(text):
            target = local_link_target(path, match.group("target"))
            if target is None:
                continue
            checked += 1
            if not target.is_relative_to(self.root):
                self.add_issue(
                    "DOC-LINK",
                    self.relative(path),
                    f"local link escapes repository: {match.group('target')!r}",
                    "link to a repository path or an explicit external URL",
                )
            elif not target.exists():
                self.add_issue(
                    "DOC-LINK",
                    self.relative(path),
                    f"broken local link {match.group('target')!r}",
                    "create the declared artifact in this Task or correct the path",
                )
        return checked

    def source_spec_metadata(self) -> dict[str, str]:
        text = self.source_spec.read_text(encoding="utf-8")
        result = {"doc_id": "SOURCE-SPEC"}
        for key in ("title", "status", "spec_version"):
            match = re.search(rf"^{key}:\s*(.+?)\s*$", text, re.MULTILINE)
            result[key] = match.group(1).strip() if match else ""
        return result

    def validate_structure(self) -> None:
        self.mark("DOC-METADATA", "DOC-ID-UNIQUE", "DOC-INVENTORY")
        docs = sorted(self.docs_root.rglob("*.md"))
        supporting = (self.root / "AGENTS.md", self.root / "README.md")
        source_metadata = self.source_spec_metadata()
        spec_version = source_metadata.get("spec_version", "")
        doc_ids: list[tuple[str, str]] = []
        links_checked = 0

        for path in (*supporting, *docs):
            text = path.read_text(encoding="utf-8")
            relative = self.relative(path)
            self.doc_texts[relative] = text
            self.validate_fences(path, text)
            links_checked += self.validate_links(path, text)

            if path == self.source_spec or path in supporting:
                continue
            metadata = parse_front_matter(text)
            self.metadata[relative] = metadata
            if not metadata:
                self.add_issue(
                    "DOC-METADATA",
                    relative,
                    "missing YAML front matter",
                    "add the required document metadata block",
                )
                continue
            missing = sorted(key for key in REQUIRED_METADATA if not metadata.get(key))
            if missing:
                self.add_issue(
                    "DOC-METADATA",
                    relative,
                    f"missing metadata values: {', '.join(missing)}",
                    "populate every required metadata key",
                )
            if spec_version and metadata.get("spec_version") != spec_version:
                self.add_issue(
                    "DOC-METADATA",
                    relative,
                    f"spec_version {metadata.get('spec_version')!r} does not match {spec_version!r}",
                    "align with the authoritative implementation spec",
                )
            if metadata.get("doc_id"):
                doc_ids.append((metadata["doc_id"], relative))

        self.absorb(duplicate_id_issues(doc_ids, check_id="DOC-ID-UNIQUE"))
        self.validate_inventory(docs, source_metadata)

        self.counts.update(
            {
                "docs": len(docs),
                "formal_docs": len(docs) - 1,
                "unique_doc_ids": len({identifier for identifier, _ in doc_ids}),
                "local_links": links_checked,
            }
        )

    def validate_inventory(
        self,
        docs: Sequence[Path],
        source_metadata: Mapping[str, str],
    ) -> None:
        inventory_text = self.inventory.read_text(encoding="utf-8")
        rows = find_table(inventory_text, {"Path", "Doc ID", "Status", "Title"})
        if rows is None:
            self.add_issue(
                "DOC-INVENTORY",
                self.relative(self.inventory),
                "document inventory table is missing or malformed",
                "restore the Path/Doc ID/Status/Title table",
            )
            return

        observed: dict[str, dict[str, str]] = {}
        for row in rows:
            link = LINK_RE.search(row["Path"])
            if link is None:
                self.add_issue(
                    "DOC-INVENTORY",
                    self.relative(self.inventory),
                    f"inventory Path cell has no Markdown link: {row['Path']!r}",
                    "use a repository-relative Markdown link",
                )
                continue
            target = local_link_target(self.inventory, link.group("target"))
            if target is None:
                continue
            observed[self.relative(target)] = row

        actual = {self.relative(path) for path in docs}
        for missing in sorted(actual - observed.keys()):
            self.add_issue(
                "DOC-INVENTORY",
                missing,
                "document is missing from inventory",
                "add one inventory row with actual metadata",
            )
        for stale in sorted(observed.keys() - actual):
            self.add_issue(
                "DOC-INVENTORY",
                stale,
                "inventory row points to a non-document path",
                "remove or correct the stale row without reusing its Doc ID",
            )

        for path in sorted(actual & observed.keys()):
            expected = source_metadata if path == self.relative(self.source_spec) else self.metadata.get(path, {})
            row = observed[path]
            comparisons = {
                "Doc ID": expected.get("doc_id", ""),
                "Status": expected.get("status", ""),
                "Title": expected.get("title", ""),
            }
            for column, value in comparisons.items():
                if row[column] != value:
                    self.add_issue(
                        "DOC-INVENTORY",
                        path,
                        f"inventory {column} {row[column]!r} does not match metadata {value!r}",
                        "synchronize the inventory row with the document front matter",
                    )
        self.counts["inventory_entries"] = len(observed)

    def registry_rows(self, path: str, headers: set[str]) -> list[dict[str, str]]:
        self.mark("REGISTRY-PARSE")
        text = self.doc_texts.get(path)
        if text is None:
            text = (self.root / path).read_text(encoding="utf-8")
        rows = find_table(text, headers)
        if rows is None:
            self.add_issue(
                "REGISTRY-PARSE",
                path,
                f"missing registry table with headers: {', '.join(sorted(headers))}",
                "restore the versioned machine-readable Markdown table",
            )
            return []
        return rows

    def validate_registry_versions(self) -> None:
        self.mark("REGISTRY-VERSION")
        for path in VERSIONED_REGISTRIES:
            metadata = self.metadata.get(path, {})
            if metadata.get("registry_version") != REGISTRY_FORMAT_VERSION:
                self.add_issue(
                    "REGISTRY-VERSION",
                    path,
                    f"registry_version must be {REGISTRY_FORMAT_VERSION!r}",
                    "set or deliberately migrate the registry format version",
                )

    def validate_registries(self) -> None:
        self.mark("REGISTRY-ID-UNIQUE", "PROD-SIM-SEPARATION", "PROD-CLOSURE")
        self.validate_registry_versions()

        req_path = "docs/governance/requirements-register.md"
        req_rows = self.registry_rows(
            req_path, {"ID", "ID status", "Requirement", "首要验收证据", "计划阶段"}
        )
        root_entries: list[tuple[str, str]] = []
        req_ids: set[str] = set()
        for row in req_rows:
            identifier = row["ID"].strip("` ")
            if re.fullmatch(r"REQ-\d{3}", identifier) is None:
                self.add_issue(
                    "REGISTRY-ID-UNIQUE",
                    req_path,
                    f"invalid Requirement ID {identifier!r}",
                    "use REQ-NNN",
                )
            if row["ID status"] not in {"ALLOCATED", "RETIRED"}:
                self.add_issue(
                    "REGISTRY-PARSE",
                    req_path,
                    f"invalid ID status {row['ID status']!r} for {identifier}",
                    "use ALLOCATED or RETIRED",
                )
            req_ids.add(identifier)
            root_entries.append((identifier, req_path))

        expected_req_ids = {f"REQ-{value:03d}" for value in range(1, 16)}
        if req_ids != expected_req_ids:
            self.add_issue(
                "REGISTRY-ID-UNIQUE",
                req_path,
                f"Requirement root set differs: missing={sorted(expected_req_ids - req_ids)}, extra={sorted(req_ids - expected_req_ids)}",
                "preserve the authoritative REQ-001 through REQ-015 set",
            )

        nfr_path = "docs/governance/nfr-and-engineering-register.md"
        nfr_rows = self.registry_rows(nfr_path, {"ID", "ID status", "要求", "可验证标准"})
        nfr_eng_ids: set[str] = set()
        for row in nfr_rows:
            identifier = row["ID"].strip("` ")
            if re.fullmatch(r"(?:NFR|ENG)-[A-Z]+-\d{3}", identifier) is None:
                self.add_issue(
                    "REGISTRY-ID-UNIQUE",
                    nfr_path,
                    f"invalid NFR/ENG ID {identifier!r}",
                    "use NFR-NAME-NNN or ENG-NAME-NNN",
                )
            if row["ID status"] not in {"ALLOCATED", "RETIRED"}:
                self.add_issue(
                    "REGISTRY-PARSE",
                    nfr_path,
                    f"invalid ID status {row['ID status']!r} for {identifier}",
                    "use ALLOCATED or RETIRED",
                )
            nfr_eng_ids.add(identifier)
            root_entries.append((identifier, nfr_path))

        self.absorb(duplicate_id_issues(root_entries))
        self.root_ids = req_ids | nfr_eng_ids

        test_path = "docs/quality/test-strategy-and-matrix.md"
        test_rows = self.registry_rows(
            test_path, {"Test ID", "Purpose", "Earliest phase", "Evidence status"}
        )
        test_entries: list[tuple[str, str]] = []
        for row in test_rows:
            identifier = row["Test ID"].strip("` ")
            if TEST_ID_RE.fullmatch(identifier) is None:
                self.add_issue(
                    "REGISTRY-ID-UNIQUE",
                    test_path,
                    f"invalid Test ID {identifier!r}",
                    "use the registered TEST prefix and a stable uppercase name",
                )
            test_entries.append((identifier, test_path))
        self.absorb(duplicate_id_issues(test_entries))
        self.test_ids = {identifier for identifier, _ in test_entries}

        open_path = "docs/governance/prod-open-register.md"
        open_rows = self.registry_rows(
            open_path, {"ID", "待确认问题", "当前状态", "主要影响"}
        )
        open_entries: list[tuple[str, str]] = []
        for row in open_rows:
            identifier = row["ID"].strip("` ")
            if OPEN_ID_RE.fullmatch(identifier) is None:
                self.add_issue(
                    "REGISTRY-ID-UNIQUE", open_path, f"invalid PROD_OPEN ID {identifier!r}", "use OPEN-NNN"
                )
            if row["当前状态"] not in {"OPEN", "CLOSED"}:
                self.add_issue(
                    "REGISTRY-PARSE",
                    open_path,
                    f"invalid PROD_OPEN status {row['当前状态']!r} for {identifier}",
                    "use OPEN or CLOSED",
                )
            if row["当前状态"] == "CLOSED":
                self.validate_closure_record(identifier, self.doc_texts[open_path])
            open_entries.append((identifier, open_path))
        self.absorb(duplicate_id_issues(open_entries))
        self.open_ids = {identifier for identifier, _ in open_entries}
        expected_open_ids = {f"OPEN-{value:03d}" for value in range(1, 16)}
        if self.open_ids != expected_open_ids:
            self.add_issue(
                "REGISTRY-ID-UNIQUE",
                open_path,
                f"PROD_OPEN root set differs: missing={sorted(expected_open_ids - self.open_ids)}, extra={sorted(self.open_ids - expected_open_ids)}",
                "preserve OPEN-001 through OPEN-015 unless an authoritative spec revision changes the set",
            )

        sim_path = "docs/governance/sim-assumption-register.md"
        sim_rows = self.registry_rows(sim_path, {"ID", "仿真假设边界", "状态", "约束"})
        sim_entries: list[tuple[str, str]] = []
        for row in sim_rows:
            identifier = row["ID"].strip("` ")
            if re.fullmatch(r"SIM-ASSUMPTION-\d{3}", identifier) is None:
                self.add_issue(
                    "REGISTRY-ID-UNIQUE",
                    sim_path,
                    f"invalid SIM_ASSUMPTION ID {identifier!r}",
                    "use SIM-ASSUMPTION-NNN",
                )
            if row["状态"] not in {"ACTIVE", "RETIRED"}:
                self.add_issue(
                    "REGISTRY-PARSE",
                    sim_path,
                    f"invalid SIM_ASSUMPTION status {row['状态']!r} for {identifier}",
                    "use ACTIVE or RETIRED",
                )
            sim_entries.append((identifier, sim_path))
        self.absorb(duplicate_id_issues(sim_entries))
        self.sim_ids = {identifier for identifier, _ in sim_entries}

        risk_path = "docs/governance/risk-register.md"
        risk_rows = self.registry_rows(risk_path, {"ID", "Status", "风险", "早期信号", "当前控制"})
        risk_entries: list[tuple[str, str]] = []
        for row in risk_rows:
            identifier = row["ID"].strip("` ")
            if RISK_ID_RE.fullmatch(identifier) is None:
                self.add_issue(
                    "REGISTRY-ID-UNIQUE", risk_path, f"invalid Risk ID {identifier!r}", "use RISK-NNN"
                )
            if row["Status"] not in {"MONITORED", "MITIGATED", "CLOSED"}:
                self.add_issue(
                    "REGISTRY-PARSE",
                    risk_path,
                    f"invalid Risk status {row['Status']!r} for {identifier}",
                    "use MONITORED, MITIGATED, or CLOSED",
                )
            risk_entries.append((identifier, risk_path))
        self.absorb(duplicate_id_issues(risk_entries))
        self.risk_ids = {identifier for identifier, _ in risk_entries}

        self.absorb(
            namespace_separation_issues(self.doc_texts[open_path], self.doc_texts[sim_path])
        )
        self.parse_impact_rules()
        self.validate_trace_matrix()
        self.collect_constraint_objective_adr_ids()

        self.counts.update(
            {
                "root_ids": len(self.root_ids),
                "test_ids": len(self.test_ids),
                "prod_open_ids": len(self.open_ids),
                "sim_assumption_ids": len(self.sim_ids),
                "risk_ids": len(self.risk_ids),
                "impact_rules": len(self.impact_rules),
            }
        )

    def validate_closure_record(self, identifier: str, text: str) -> None:
        self.mark("PROD-CLOSURE")
        heading = re.search(
            rf"^###\s+{re.escape(identifier)}\s+closure\s*$", text, re.MULTILINE | re.IGNORECASE
        )
        required_labels = (
            "Authority",
            "Evidence",
            "Decision date",
            "Decision",
            "Applies to",
            "Affected artifacts",
            "Migration/replay",
        )
        if heading is None:
            self.add_issue(
                "PROD-CLOSURE",
                "docs/governance/prod-open-register.md",
                f"{identifier} is CLOSED without a closure record",
                "add the required authority/evidence/decision record before closing",
            )
            return
        section = text[heading.end() :]
        next_heading = re.search(r"^###\s+", section, re.MULTILINE)
        if next_heading:
            section = section[: next_heading.start()]
        missing = [label for label in required_labels if not re.search(rf"^{re.escape(label)}:\s*\S", section, re.MULTILINE)]
        if missing:
            self.add_issue(
                "PROD-CLOSURE",
                "docs/governance/prod-open-register.md",
                f"{identifier} closure record misses: {', '.join(missing)}",
                "complete every required closure evidence field",
            )

    def parse_impact_rules(self) -> None:
        path = "docs/governance/change-impact-matrix.md"
        rows = self.registry_rows(path, {"Rule ID", "Changed path globs", "Required documentation"})
        entries: list[tuple[str, str]] = []
        rules: list[ImpactRule] = []
        for row in rows:
            rule_id = row["Rule ID"].strip("` ")
            patterns = tuple(normalize_repo_path(value) for value in extract_backtick_values(row["Changed path globs"]))
            required_docs = tuple(normalize_repo_path(value) for value in extract_backtick_values(row["Required documentation"]))
            if IMPACT_ID_RE.fullmatch(rule_id) is None or not patterns or not required_docs:
                self.add_issue(
                    "REGISTRY-PARSE",
                    path,
                    f"invalid impact rule {rule_id!r}",
                    "provide a stable IMPACT-* ID, at least one glob, and exact required docs",
                )
            for document in required_docs:
                if not (self.root / document).exists():
                    self.add_issue(
                        "TRACE-PATH",
                        path,
                        f"impact rule {rule_id} references missing document {document!r}",
                        "create the document in the owning Task or correct the rule",
                    )
            entries.append((rule_id, path))
            rules.append(ImpactRule(rule_id, patterns, required_docs))
        self.absorb(duplicate_id_issues(entries))
        self.impact_rules = rules

    def validate_trace_matrix(self) -> None:
        self.mark("TRACE-COVERAGE", "TRACE-PATH")
        path = "docs/governance/traceability-matrix.md"
        rows = self.registry_rows(
            path, {"Root", "Kind", "Normative landing", "Planned milestone / first task", "Evidence state"}
        )
        entries: list[tuple[str, str]] = []
        matrix_ids: set[str] = set()
        for row in rows:
            identifier = row["Root"].strip("` ")
            entries.append((identifier, path))
            matrix_ids.add(identifier)
            expected_kind = identifier.split("-", 1)[0]
            if row["Kind"] != expected_kind:
                self.add_issue(
                    "TRACE-COVERAGE",
                    path,
                    f"{identifier} kind {row['Kind']!r} should be {expected_kind!r}",
                    "align the matrix Kind with the root prefix",
                )
            normative_paths = [
                normalize_repo_path(value)
                for value in extract_backtick_values(row["Normative landing"])
                if value.endswith(".md")
            ]
            if not normative_paths:
                self.add_issue(
                    "TRACE-PATH",
                    path,
                    f"{identifier} has no exact normative document path",
                    "add at least one repository-relative docs/*.md path",
                )
            for normative_path in normative_paths:
                if not (self.root / normative_path).is_file():
                    self.add_issue(
                        "TRACE-PATH",
                        path,
                        f"{identifier} normative path does not exist: {normative_path!r}",
                        "remove fabricated paths or create the artifact in its authorized Task",
                    )
        self.absorb(duplicate_id_issues(entries))
        if matrix_ids != self.root_ids:
            self.add_issue(
                "TRACE-COVERAGE",
                path,
                f"trace roots differ: missing={sorted(self.root_ids - matrix_ids)}, extra={sorted(matrix_ids - self.root_ids)}",
                "keep exactly one matrix row for every registered REQ/NFR/ENG root",
            )
        self.counts["trace_rows"] = len(rows)

    def collect_constraint_objective_adr_ids(self) -> None:
        constraint_path = "docs/planning/constraint-catalog.md"
        constraint_ids: set[str] = set()
        for rows in parse_markdown_tables(self.doc_texts[constraint_path]):
            if not rows or "ID" not in rows[0]:
                continue
            for row in rows:
                identifier = row["ID"].strip("` ")
                if CONSTRAINT_ID_RE.fullmatch(identifier):
                    constraint_ids.add(identifier)
        self.constraint_ids = constraint_ids

        objective_text = self.doc_texts["docs/planning/objective-policy.md"]
        self.objective_ids = set(OBJECTIVE_ID_RE.findall(objective_text))

        self.adr_ids = {
            metadata["doc_id"]
            for path, metadata in self.metadata.items()
            if path.startswith("docs/adr/ADR-") and ADR_ID_RE.fullmatch(metadata.get("doc_id", ""))
        }

    def validate_tasks(self) -> None:
        self.mark("TASK-FIELDS", "TASK-REFERENCES", "TASK-DEPENDENCY", "PHASE-TASK")
        task_paths = sorted(self.docs_root.glob("tasks/*/TASK-*.md"))
        task_by_id: dict[str, Path] = {}
        status_by_id: dict[str, str] = {}

        current_phase = self.metadata.get("docs/current_phase.md", {}).get("phase", "")
        current_phase_number = phase_number(current_phase)
        if current_phase_number is None:
            self.add_issue(
                "PHASE-TASK",
                "docs/current_phase.md",
                f"invalid current phase {current_phase!r}",
                "set front matter phase to an exact Pn identifier",
            )
            current_phase_number = 0
        self.current_phase = current_phase

        for path in task_paths:
            relative = self.relative(path)
            text = self.doc_texts[relative]
            metadata = self.metadata.get(relative, {})
            task_id = metadata.get("doc_id", "")
            status = metadata.get("status", "")
            if TASK_ID_RE.fullmatch(task_id) is None:
                self.add_issue(
                    "TASK-REFERENCES", relative, f"invalid Task doc_id {task_id!r}", "use TASK-Pn-NN"
                )
            if status not in TASK_STATUSES:
                self.add_issue(
                    "TASK-FIELDS",
                    relative,
                    f"invalid Task status {status!r}",
                    f"use one of {sorted(TASK_STATUSES)}",
                )
            task_by_id[task_id] = path
            status_by_id[task_id] = status

            folder_phase = path.parent.name
            metadata_phase = metadata.get("phase", "")
            phase_issue = task_phase_policy_issue(
                task_id,
                folder_phase,
                metadata_phase,
                current_phase,
                status,
            )
            if phase_issue is not None:
                message, suggestion = phase_issue
                self.add_issue(
                    "PHASE-TASK",
                    relative,
                    message,
                    suggestion,
                )

        self.task_ids = set(task_by_id)
        current_tasks: list[str] = []
        for task_id, path in task_by_id.items():
            relative = self.relative(path)
            text = self.doc_texts[relative]
            status = status_by_id[task_id]
            task_match = re.fullmatch(r"TASK-(P\d+)-\d{2}", task_id)
            task_phase_number = (
                phase_number(task_match.group(1)) if task_match is not None else None
            )
            if status == "in_progress":
                current_tasks.append(task_id)
                diff_base = extract_task_field(text, "Diff base")
                if not diff_base:
                    self.add_issue(
                        "TASK-FIELDS",
                        relative,
                        "in_progress Task has no Diff base",
                        "record the full immutable HEAD commit before implementation",
                    )
                elif COMMIT_SHA_RE.fullmatch(diff_base) is None:
                    self.add_issue(
                        "TASK-FIELDS",
                        relative,
                        "in_progress Task Diff base is not a full 40-character commit SHA",
                        "record the full immutable HEAD commit before implementation",
                    )

            missing = missing_task_fields(text)
            if task_phase_number is not None and task_phase_number >= 1:
                missing.extend(
                    field
                    for field in P1_REQUIRED_TASK_FIELDS
                    if not extract_task_field(text, field)
                )
            if task_phase_number is not None and task_phase_number >= 2:
                missing.extend(
                    field
                    for field in P2_REQUIRED_TASK_FIELDS
                    if not extract_task_field(text, field)
                )
            if missing:
                self.add_issue(
                    "TASK-FIELDS",
                    relative,
                    f"missing or empty Task fields: {', '.join(missing)}",
                    "fill every required field before implementation",
                )

            requirement_refs = expand_numeric_ranges(
                extract_task_field(text, "Requirement IDs"), "REQ-", 3
            )
            unknown_requirements = sorted(requirement_refs - self.root_ids)
            if unknown_requirements:
                self.add_issue(
                    "TASK-REFERENCES",
                    relative,
                    f"unknown Requirement IDs: {', '.join(unknown_requirements)}",
                    "use registered REQ IDs",
                )

            nfr_field = extract_task_field(text, "NFR / ENG IDs")
            if "all registered" not in nfr_field.lower():
                nfr_refs = set(ROOT_ID_RE.findall(nfr_field))
                unknown_nfr = sorted(nfr_refs - self.root_ids)
                if unknown_nfr:
                    self.add_issue(
                        "TASK-REFERENCES",
                        relative,
                        f"unknown NFR/ENG IDs: {', '.join(unknown_nfr)}",
                        "use registered NFR/ENG IDs",
                    )

            dependency_field = extract_task_field(text, "Depends on")
            dependency_ids = expand_task_ranges(dependency_field)
            unknown_dependencies = sorted(dependency_ids - self.task_ids)
            if unknown_dependencies:
                self.add_issue(
                    "TASK-REFERENCES",
                    relative,
                    f"unknown Task dependencies: {', '.join(unknown_dependencies)}",
                    "reference an existing Task Card",
                )
            for value in extract_backtick_values(dependency_field):
                normalized = normalize_repo_path(value)
                if normalized.endswith(".md") and not (self.root / normalized).exists():
                    self.add_issue(
                        "TASK-REFERENCES",
                        relative,
                        f"dependency path does not exist: {normalized!r}",
                        "correct the path before starting the Task",
                    )
            if status in {"in_progress", "done"}:
                incomplete = sorted(
                    dependency
                    for dependency in dependency_ids
                    if status_by_id.get(dependency) != "done"
                )
                if incomplete:
                    self.add_issue(
                        "TASK-DEPENDENCY",
                        relative,
                        f"active/completed Task has incomplete dependencies: {', '.join(incomplete)}",
                        "complete dependencies or return this Task to planned/blocked",
                    )

            documents_field = extract_task_field(text, "Documents to update")
            document_paths = {
                normalize_repo_path(value)
                for value in extract_backtick_values(documents_field)
                if value.endswith(".md")
            }
            document_paths.add(relative)
            if status in {"in_progress", "done"}:
                missing_documents = sorted(
                    document for document in document_paths if not (self.root / document).exists()
                )
                if missing_documents:
                    self.add_issue(
                        "TASK-REFERENCES",
                        relative,
                        f"active/completed Task declares missing documents: {', '.join(missing_documents)}",
                        "create the documents inside this Task or correct the declarations",
                    )
            files_allowed = extract_task_field(text, "Files allowed to change")
            if "Documents to update" not in files_allowed:
                self.add_issue(
                    "TASK-FIELDS",
                    relative,
                    "Files allowed to change does not include Documents to update",
                    "explicitly include the Task's document list in the allowed boundary",
                )

            documentation_impact = extract_task_field(text, "Documentation impact")
            if not (documentation_impact.startswith("required") or documentation_impact.startswith("none")):
                self.add_issue(
                    "TASK-FIELDS",
                    relative,
                    f"invalid Documentation impact {documentation_impact!r}",
                    "declare required or none",
                )
            if documentation_impact.startswith("none") and not extract_task_field(
                text, "Documentation impact rationale"
            ):
                self.add_issue(
                    "TASK-FIELDS",
                    relative,
                    "Documentation impact none has no rationale",
                    "record a verifiable reason and reviewed impact rows",
                )

            self.task_records[task_id] = {
                "path": relative,
                "status": status,
                "text": text,
                "documents": document_paths,
                "allowed": {
                    normalize_repo_path(value)
                    for value in extract_backtick_values(files_allowed)
                },
            }

        if len(current_tasks) > 1:
            self.add_issue(
                "PHASE-TASK",
                f"docs/tasks/{current_phase}",
                f"multiple Tasks are in_progress: {', '.join(sorted(current_tasks))}",
                "keep at most one active Task",
            )
        if self.task_path is None and self.task_discovery_base is not None:
            try:
                discovered = self.discover_changed_task_path(
                    self.task_discovery_base, current_phase
                )
            except (RuntimeError, TaskDiscoveryError) as error:
                self.add_issue(
                    "PHASE-TASK",
                    "Task discovery",
                    str(error),
                    "provide an immutable event base whose range changes exactly one current-phase Task Card",
                )
            else:
                if discovered is not None:
                    self.task_path = (self.root / discovered).resolve()
        if self.task_path is None and len(current_tasks) == 1:
            self.task_path = task_by_id[current_tasks[0]].resolve()
        if (
            self.task_path is None
            and self.task_discovery_base is not None
            and len(current_tasks) != 1
        ):
            self.add_issue(
                "PHASE-TASK",
                "Task discovery",
                f"change range contains no current {current_phase} Task Card and no unique in_progress fallback",
                "change the current Task Card in the event range or keep exactly one current Task in_progress",
            )
        self.counts["tasks"] = len(task_paths)

    def reference_documents(self) -> dict[str, str]:
        documents = dict(self.doc_texts)
        for path in sorted((self.root / "scripts").rglob("*.py")):
            documents[self.relative(path)] = path.read_text(encoding="utf-8")
        tests_root = self.root / "backend" / "tests"
        if tests_root.exists():
            for path in sorted(tests_root.rglob("*.py")):
                documents[self.relative(path)] = path.read_text(encoding="utf-8")
        return documents

    def validate_references(self) -> None:
        self.mark("REFERENCE-VALID")
        documents = self.reference_documents()
        namespaces: tuple[
            tuple[set[str], re.Pattern[str], Callable[[str], str] | None], ...
        ] = (
            (self.root_ids, ROOT_ID_RE, None),
            (self.test_ids, TEST_ID_RE, None),
            (self.task_ids, TASK_ID_RE, None),
            (self.constraint_ids, CONSTRAINT_ID_RE, None),
            (self.objective_ids, OBJECTIVE_ID_RE, None),
            (self.adr_ids, ADR_ID_RE, None),
            (self.open_ids, OPEN_ID_RE, None),
            (
                self.sim_ids,
                SIM_ID_RE,
                lambda value: value.replace("SIM_ASSUMPTION-", "SIM-ASSUMPTION-"),
            ),
            (self.risk_ids, RISK_ID_RE, None),
        )
        for known_ids, pattern, normalize in namespaces:
            self.absorb(
                unknown_reference_issues(
                    documents,
                    known_ids,
                    pattern,
                    normalize=normalize,
                )
            )

    def git_output(self, *args: str) -> str:
        result = subprocess.run(
            ["git", "-c", "core.quotepath=false", *args],
            cwd=self.root,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "git command failed")
        return result.stdout

    def discover_changed_task_path(
        self, change_base: str, current_phase: str
    ) -> str | None:
        """Discover a current Task from one immutable CI event range."""

        if COMMIT_SHA_RE.fullmatch(change_base) is None:
            raise TaskDiscoveryError(
                "CI Task discovery base is not a full 40-character commit SHA"
            )
        resolved_base = self.git_output(
            "rev-parse", "--verify", f"{change_base}^{{commit}}"
        ).strip()
        self.git_output("merge-base", "--is-ancestor", resolved_base, "HEAD")
        self.task_discovery_base = resolved_base.lower()
        changed_output = self.git_output(
            "diff",
            "--name-only",
            "--diff-filter=ACDMRTUXB",
            f"{resolved_base}..HEAD",
            "--",
            "docs/tasks",
        )
        added_output = self.git_output(
            "diff",
            "--name-only",
            "--diff-filter=A",
            f"{resolved_base}..HEAD",
            "--",
            "docs/tasks",
        )
        changed_task_paths = [
            normalize_repo_path(path)
            for path in changed_output.splitlines()
            if path.strip()
        ]
        task_texts = {
            path: (self.root / path).read_text(encoding="utf-8")
            for path in changed_task_paths
            if (self.root / path).is_file()
        }
        normalized_added = {
            normalize_repo_path(path)
            for path in added_output.splitlines()
            if path.strip()
        }
        base_task_texts: dict[str, str] = {}
        logical_task_ids = {
            f"TASK-{match.group('id_phase')}-{match.group('number')}"
            for path in changed_task_paths
            if (match := TASK_CARD_PATH_RE.fullmatch(path)) is not None
        }
        if len(logical_task_ids) > 1 and not set(changed_task_paths).issubset(
            normalized_added
        ):
            base_paths_output = self.git_output(
                "ls-tree",
                "-r",
                "--name-only",
                resolved_base,
                "--",
                f"docs/tasks/{current_phase}",
            )
            for raw_path in base_paths_output.splitlines():
                path = normalize_repo_path(raw_path)
                match = TASK_CARD_PATH_RE.fullmatch(path)
                if match is None:
                    continue
                task_id = f"TASK-{match.group('id_phase')}-{match.group('number')}"
                if task_id not in logical_task_ids:
                    continue
                base_task_texts[path] = self.git_output(
                    "show", f"{resolved_base}:{path}"
                )
        selected = select_changed_task_path(
            changed_task_paths,
            current_phase,
            added_paths=normalized_added,
            task_texts=task_texts,
            base_task_texts=base_task_texts,
        )
        if selected is not None and not (self.root / selected).is_file():
            raise TaskDiscoveryError(f"discovered Task Card does not exist: {selected}")
        return selected

    def git_changed_paths(self, diff_base: str | None = None) -> list[str]:
        """Return the Task range union the current tracked/untracked working tree."""

        committed_paths: set[str] = set()
        if diff_base is not None:
            committed_output = self.git_output(
                "diff",
                "--name-only",
                "--diff-filter=ACDMRTUXB",
                f"{diff_base}..HEAD",
                "--",
            )
            committed_paths = {
                normalize_repo_path(line)
                for line in committed_output.splitlines()
                if line.strip()
            }

        working_output = self.git_output(
            "status", "--porcelain=v1", "--untracked-files=all"
        )
        working_paths: set[str] = set()
        for line in working_output.splitlines():
            if len(line) < 4:
                continue
            value = line[3:]
            if " -> " in value:
                value = value.split(" -> ", 1)[1]
            working_paths.add(normalize_repo_path(value.strip('"')))

        self.diff_source_counts = {
            "committed_range": len(committed_paths),
            "working_tree": len(working_paths),
        }
        return sorted(committed_paths | working_paths)

    def validate_diff(self) -> None:
        self.mark("DIFF-IMPACT", "TASK-SCOPE")
        if self.task_path is None:
            self.add_issue(
                "DIFF-IMPACT",
                "Task Card",
                "--check-diff requires --task or exactly one in_progress Task",
                "pass the current Task Card path",
            )
            return
        task_relative = self.relative(self.task_path)
        task_metadata = self.metadata.get(task_relative, {})
        task_id = task_metadata.get("doc_id", "")
        task_record = self.task_records.get(task_id)
        if task_record is None:
            self.add_issue(
                "DIFF-IMPACT",
                task_relative,
                "selected Task Card was not parsed",
                f"select a current {self.current_phase or 'phase'} Task Card",
            )
            return

        text = str(task_record["text"])
        declared_rule_ids = set(
            IMPACT_ID_RE.findall(extract_task_field(text, "Change-impact matrix rows reviewed"))
        )
        known_rule_ids = {rule.rule_id for rule in self.impact_rules}
        unknown_rules = sorted(declared_rule_ids - known_rule_ids)
        if unknown_rules:
            self.add_issue(
                "DIFF-IMPACT",
                task_relative,
                f"Task declares unknown impact rules: {', '.join(unknown_rules)}",
                "use Rule IDs from change-impact-matrix.md",
            )

        diff_base_value = extract_task_field(text, "Diff base")
        valid_diff_base: str | None = None
        if diff_base_value:
            self.diff_base = diff_base_value.lower()
            if COMMIT_SHA_RE.fullmatch(diff_base_value) is None:
                self.add_issue(
                    "DIFF-IMPACT",
                    task_relative,
                    "Diff base is not a full 40-character Git commit SHA",
                    "record the immutable HEAD commit from immediately before the Task started",
                )
            else:
                try:
                    resolved_base = self.git_output(
                        "rev-parse", "--verify", f"{diff_base_value}^{{commit}}"
                    ).strip()
                    self.git_output("merge-base", "--is-ancestor", resolved_base, "HEAD")
                except RuntimeError as error:
                    self.add_issue(
                        "DIFF-IMPACT",
                        task_relative,
                        f"Diff base cannot define a valid ancestor range: {error}",
                        "use the immutable commit that was HEAD immediately before the Task started",
                    )
                else:
                    valid_diff_base = resolved_base.lower()
                    self.diff_base = valid_diff_base

        changed_paths = self.git_changed_paths(valid_diff_base)
        if not changed_paths and not diff_base_value:
            self.add_issue(
                "DIFF-IMPACT",
                task_relative,
                "no working-tree changes and no Diff base are available for Task impact validation",
                "record the immutable pre-Task commit in the Task Card as Diff base",
            )
        documents = set(cast(set[str], task_record["documents"]))
        coverage = evaluate_impact_coverage(
            changed_paths, self.impact_rules, declared_rule_ids, documents
        )
        self.absorb(coverage.issues)
        self.changed_paths = changed_paths
        self.matched_impact_rows = list(coverage.matched_rule_ids)
        self.expected_docs = list(coverage.expected_docs)
        self.observed_docs = sorted(set(changed_paths) & set(coverage.expected_docs))

        allowed = set(cast(set[str], task_record["allowed"]))
        allowed.update(documents)
        allowed.add(task_relative)
        for changed_path in changed_paths:
            if changed_path.endswith("/.gitkeep"):
                continue
            if changed_path not in allowed:
                self.add_issue(
                    "TASK-SCOPE",
                    changed_path,
                    f"changed path is outside {task_id} explicit allowed boundary",
                    "revert it or revise the Task Card before continuing",
                )

    def build_report(self, check_diff: bool) -> dict[str, object]:
        failed_checks = {issue.check_id for issue in self.issues}
        checks = []
        for check_id, description in CHECK_DESCRIPTIONS.items():
            if check_id not in self.executed_checks:
                status = "NOT_RUN"
            elif check_id in failed_checks:
                status = "FAIL"
            else:
                status = "PASS"
            checks.append({"check_id": check_id, "description": description, "status": status})

        task_id = None
        if self.task_path is not None:
            task_id = self.metadata.get(self.relative(self.task_path), {}).get("doc_id")
        try:
            git_head = self.git_output("rev-parse", "HEAD").strip()
        except RuntimeError:
            git_head = None

        return {
            "schema_version": REPORT_SCHEMA_VERSION,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "result": "PASS" if not self.issues else "FAIL",
            "task": task_id,
            "task_discovery_base": self.task_discovery_base,
            "git_head": git_head,
            "diff_base": self.diff_base,
            "diff_source_counts": dict(sorted(self.diff_source_counts.items())),
            "diff_checked": check_diff,
            "changed_paths": self.changed_paths,
            "matched_impact_rows": self.matched_impact_rows,
            "expected_documents": self.expected_docs,
            "observed_documents": self.observed_docs,
            "missing_trace_refs": sorted(self.missing_trace_refs),
            "counts": dict(sorted(self.counts.items())),
            "checks": checks,
            "issues": [asdict(issue) for issue in self.issues],
        }

    def run(self, *, check_diff: bool = False) -> dict[str, object]:
        self.validate_structure()
        self.validate_registries()
        self.validate_tasks()
        self.validate_references()
        if check_diff:
            self.validate_diff()
        return self.build_report(check_diff)


def write_report(path: Path, report: Mapping[str, object], repository_root: Path) -> None:
    """Write a structured report only inside the repository."""

    resolved = path.resolve()
    root = repository_root.resolve()
    if not resolved.is_relative_to(root):
        raise ValueError("report path must remain inside the repository")
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def print_text_report(report: Mapping[str, object], report_path: Path | None) -> None:
    """Print a concise human-readable validation result."""

    counts = report["counts"]
    assert isinstance(counts, dict)
    summary = (
        f"{report['result']} repository governance: "
        f"docs={counts.get('docs', 0)} roots={counts.get('root_ids', 0)} "
        f"trace_rows={counts.get('trace_rows', 0)} tests={counts.get('test_ids', 0)} "
        f"open={counts.get('prod_open_ids', 0)} sim={counts.get('sim_assumption_ids', 0)} "
        f"risks={counts.get('risk_ids', 0)} tasks={counts.get('tasks', 0)} "
        f"task={report.get('task') or 'none'}"
    )
    if report.get("diff_checked"):
        changed_paths = cast(Sequence[object], report.get("changed_paths", []))
        matched_rows = cast(Sequence[object], report.get("matched_impact_rows", []))
        summary += (
            f" diff_paths={len(changed_paths)}"
            f" impact_rows={len(matched_rows)}"
        )
    print(summary)
    issues = report.get("issues", [])
    if isinstance(issues, list):
        for item in issues:
            if isinstance(item, dict):
                print(
                    f"- [{item['check_id']}] {item['path']}: {item['message']} "
                    f"Fix: {item['suggestion']}"
                )
    if report_path is not None:
        print(f"Report: {report_path.as_posix()}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    task_selection = parser.add_mutually_exclusive_group()
    task_selection.add_argument(
        "--task",
        type=Path,
        help="Current Task Card path; inferred when exactly one Task is in_progress.",
    )
    task_selection.add_argument(
        "--discover-task-from",
        metavar="COMMIT_SHA",
        help="Discover one current-phase Task Card changed since an immutable CI event base.",
    )
    parser.add_argument(
        "--check-diff",
        action="store_true",
        help="Match the Task's Diff base..HEAD plus working tree to impact rules.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        help="Write a traceability-report.v1 JSON artifact inside the repository.",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Stdout format.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.discover_task_from is not None and not args.check_diff:
        parser.error("--discover-task-from requires --check-diff")
    repository_root = Path(__file__).resolve().parents[1]
    task_path = None
    if args.task is not None:
        task_path = args.task if args.task.is_absolute() else repository_root / args.task
    validator = RepositoryValidator(
        repository_root,
        task_path,
        task_discovery_base=args.discover_task_from,
    )
    report = validator.run(check_diff=args.check_diff)

    report_path = None
    if args.report is not None:
        report_path = args.report if args.report.is_absolute() else repository_root / args.report
        try:
            write_report(report_path, report, repository_root)
        except ValueError as error:
            print(f"FAIL repository governance: {error}", file=sys.stderr)
            return 2

    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        display_path = report_path.relative_to(repository_root) if report_path else None
        print_text_report(report, display_path)
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
