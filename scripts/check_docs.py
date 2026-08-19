"""Run the structural documentation checks established by TASK-P0-01."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DOCS_ROOT = REPOSITORY_ROOT / "docs"
SOURCE_SPEC = DOCS_ROOT / "core" / "APS_IMPLEMENTATION_SPEC.md"
INVENTORY = DOCS_ROOT / "governance" / "document-inventory.md"
ROOT_MARKDOWN = (REPOSITORY_ROOT / "AGENTS.md", REPOSITORY_ROOT / "README.md")

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

FRONT_MATTER_RE = re.compile(r"\A---\s*\n(?P<body>.*?)\n---\s*\n", re.DOTALL)
LINK_RE = re.compile(r"!?\[[^\]]*\]\((?P<target>[^)]+)\)")
FENCE_RE = re.compile(r"^\s*(```|~~~)")


def relative(path: Path) -> str:
    """Return a stable repository-relative path for diagnostics."""

    return path.relative_to(REPOSITORY_ROOT).as_posix()


def parse_front_matter(path: Path, text: str, failures: list[str]) -> dict[str, str]:
    """Parse the simple top-level YAML keys used by repository documents."""

    match = FRONT_MATTER_RE.match(text)
    if match is None:
        failures.append(f"{relative(path)}: missing YAML front matter")
        return {}

    metadata: dict[str, str] = {}
    for line in match.group("body").splitlines():
        if not line or line[0].isspace() or ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip()

    missing = sorted(key for key in REQUIRED_METADATA if not metadata.get(key))
    if missing:
        failures.append(
            f"{relative(path)}: missing metadata values: {', '.join(missing)}"
        )
    return metadata


def check_fences(path: Path, text: str, failures: list[str]) -> None:
    """Check that Markdown code fences open and close with the same marker."""

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
            failures.append(
                f"{relative(path)}:{line_number}: fence {marker!r} closes {active!r}"
            )
    if active is not None:
        failures.append(f"{relative(path)}: unclosed {active!r} fence")


def local_link_target(source: Path, raw_target: str) -> Path | None:
    """Resolve a local Markdown link, ignoring URLs and same-page anchors."""

    target = raw_target.strip()
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1]
    target = unquote(target.split("#", 1)[0].strip())
    if not target or re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target):
        return None
    return (source.parent / target).resolve()


def check_links(path: Path, text: str, failures: list[str]) -> int:
    """Validate local Markdown link targets and return the number checked."""

    checked = 0
    for match in LINK_RE.finditer(text):
        target = local_link_target(path, match.group("target"))
        if target is None:
            continue
        checked += 1
        if not target.exists():
            failures.append(
                f"{relative(path)}: broken local link {match.group('target')!r}"
            )
    return checked


def source_spec_version(failures: list[str]) -> str:
    """Read the version declared by the authoritative implementation spec."""

    text = SOURCE_SPEC.read_text(encoding="utf-8")
    match = re.search(r"^spec_version:\s*(\S+)\s*$", text, re.MULTILINE)
    if match is None:
        failures.append(f"{relative(SOURCE_SPEC)}: spec_version is missing")
        return ""
    return match.group(1)


def check_task_fields(path: Path, text: str, failures: list[str]) -> None:
    """Ensure each current P0 Task Card exposes all governance fields."""

    for field in REQUIRED_TASK_FIELDS:
        if re.search(rf"^{re.escape(field)}:\s*\S", text, re.MULTILINE) is None:
            failures.append(f"{relative(path)}: missing or empty Task field {field!r}")


def inventory_paths(text: str) -> set[Path]:
    """Return the docs files linked by the document inventory."""

    paths: set[Path] = set()
    for match in LINK_RE.finditer(text):
        target = local_link_target(INVENTORY, match.group("target"))
        if target is not None and target.suffix.lower() == ".md":
            paths.add(target)
    return paths


def main() -> int:
    """Run all P0-01 document checks."""

    failures: list[str] = []
    docs = sorted(DOCS_ROOT.rglob("*.md"))
    spec_version = source_spec_version(failures)
    doc_ids: dict[str, Path] = {}
    links_checked = 0
    formal_docs = 0

    for path in ROOT_MARKDOWN:
        text = path.read_text(encoding="utf-8")
        check_fences(path, text, failures)
        links_checked += check_links(path, text, failures)

    for path in docs:
        text = path.read_text(encoding="utf-8")
        check_fences(path, text, failures)
        links_checked += check_links(path, text, failures)

        if path != SOURCE_SPEC:
            formal_docs += 1
            metadata = parse_front_matter(path, text, failures)
            doc_id = metadata.get("doc_id")
            if doc_id:
                previous = doc_ids.get(doc_id)
                if previous is not None:
                    failures.append(
                        f"{relative(path)}: duplicate doc_id {doc_id!r}; "
                        f"first declared by {relative(previous)}"
                    )
                else:
                    doc_ids[doc_id] = path
            if spec_version and metadata.get("spec_version") != spec_version:
                failures.append(
                    f"{relative(path)}: spec_version {metadata.get('spec_version')!r} "
                    f"does not match {spec_version!r}"
                )

        if path.parent == DOCS_ROOT / "tasks" / "P0" and path.name.startswith("TASK-"):
            check_task_fields(path, text, failures)

    inventory_text = INVENTORY.read_text(encoding="utf-8")
    listed_docs = inventory_paths(inventory_text)
    actual_docs = set(docs)
    for missing in sorted(actual_docs - listed_docs):
        failures.append(f"{relative(missing)}: missing from document inventory")
    for stale in sorted(listed_docs - actual_docs):
        failures.append(f"{relative(stale)}: stale document inventory entry")

    if failures:
        print(f"FAIL document consistency: {len(failures)} issue(s)")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print(
        "PASS document consistency: "
        f"docs={len(docs)} formal_docs={formal_docs} unique_doc_ids={len(doc_ids)} "
        f"local_links={links_checked} tasks=9 inventory_entries={len(listed_docs)} "
        f"spec_version={spec_version}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
