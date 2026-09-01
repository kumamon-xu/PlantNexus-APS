"""TEST-PHASE-GOVERNANCE-001 CI validation profile routing tests."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from scripts.ci_validation_profile import (
    DOCS_ONLY,
    FULL,
    ChangeEntry,
    GitRepository,
    classify_entries,
    classify_repository,
    is_public_markdown,
    main,
    parse_name_status_z,
    validate_public_docs,
)


TEST_ID = "TEST-PHASE-GOVERNANCE-001"


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


def commit(root: Path, message: str) -> str:
    git(root, "add", "-A")
    git(root, "commit", "-m", message)
    return git(root, "rev-parse", "HEAD")


@pytest.fixture
def repository_root() -> Iterator[Path]:
    with TemporaryDirectory() as temporary_directory:
        root = Path(temporary_directory)
        git(root, "init")
        git(root, "config", "user.name", "PlantNexus Test")
        git(root, "config", "user.email", "plantnexus-test@example.invalid")
        yield root


def test_public_markdown_allow_list_excludes_internal_process_documents() -> None:
    assert is_public_markdown("README.md")
    assert is_public_markdown("docs/README.md")
    assert is_public_markdown("docs/architecture/system-context.md")
    assert not is_public_markdown("docs/tasks/P4/TASK-P4-16.md")
    assert not is_public_markdown("docs/governance/change-impact-matrix.md")
    assert not is_public_markdown("docs/adr/ADR_TEMPLATE.md")
    assert not is_public_markdown("docs/core/APS_IMPLEMENTATION_SPEC.md")
    assert not is_public_markdown("docs/architecture/config.json")
    assert not is_public_markdown("AGENTS.md")


@pytest.mark.parametrize(
    "path",
    (
        "backend/app/service.py",
        "backend/tests/unit/test_service.py",
        ".github/workflows/ci.yml",
        "scripts/ci_validation_profile.py",
        "pyproject.toml",
        "uv.lock",
        "docs/.gitignore",
        "docs/tasks/P4/TASK-P4-16.md",
    ),
)
def test_any_non_public_markdown_path_forces_full(path: str) -> None:
    profile, reason = classify_entries((ChangeEntry("M", (path,)),))

    assert profile == FULL
    assert path in reason


def test_only_public_markdown_paths_select_docs_only() -> None:
    profile, _reason = classify_entries(
        (
            ChangeEntry("M", ("README.md",)),
            ChangeEntry("A", ("docs/contracts/new-contract.md",)),
            ChangeEntry(
                "R100",
                (
                    "docs/architecture/old-name.md",
                    "docs/architecture/new-name.md",
                ),
            ),
        )
    )

    assert profile == DOCS_ONLY


def test_empty_or_unmerged_diff_forces_full() -> None:
    assert classify_entries(())[0] == FULL
    assert (
        classify_entries((ChangeEntry("U", ("docs/architecture/conflict.md",)),))[0]
        == FULL
    )


def test_name_status_parser_preserves_both_rename_paths() -> None:
    entries = parse_name_status_z(
        "M\0README.md\0R100\0docs/architecture/a.md\0"
        "docs/architecture/b.md\0"
    )

    assert entries == (
        ChangeEntry("M", ("README.md",)),
        ChangeEntry(
            "R100", ("docs/architecture/a.md", "docs/architecture/b.md")
        ),
    )


@pytest.mark.parametrize(
    "output",
    ("M\0README.md", "Q\0README.md\0", "R100\0docs/architecture/a.md\0"),
)
def test_name_status_parser_rejects_malformed_input(output: str) -> None:
    with pytest.raises(ValueError):
        parse_name_status_z(output)


def test_repository_classifier_and_docs_validator_accept_valid_change(
    repository_root: Path,
) -> None:
    write(
        repository_root,
        "docs/architecture/a.md",
        "# A\n\nSee [B](b.md#contract).\n",
    )
    write(repository_root, "docs/architecture/b.md", "# B\n")
    base_sha = commit(repository_root, "base")
    write(
        repository_root,
        "docs/architecture/a.md",
        "# A\n\nSee [B](b.md#contract).\n\nClarified.\n",
    )
    head_sha = commit(repository_root, "docs")
    repository = GitRepository(repository_root)

    classification = classify_repository(repository, base_sha, head_sha)
    report = validate_public_docs(repository, classification)

    assert classification.profile == DOCS_ONLY
    assert report["result"] == "PASS"
    assert report["issues"] == []


def test_docs_validator_rejects_a_new_broken_link(repository_root: Path) -> None:
    write(repository_root, "docs/architecture/a.md", "# A\n")
    base_sha = commit(repository_root, "base")
    write(
        repository_root,
        "docs/architecture/a.md",
        "# A\n\n[Missing](missing.md)\n",
    )
    head_sha = commit(repository_root, "broken link")
    repository = GitRepository(repository_root)

    report = validate_public_docs(
        repository, classify_repository(repository, base_sha, head_sha)
    )

    assert report["result"] == "FAIL"
    assert report["issues"][0]["check_id"] == "PUBLIC-DOC-LINK"


def test_docs_validator_rejects_deletion_that_breaks_an_inbound_link(
    repository_root: Path,
) -> None:
    write(repository_root, "docs/architecture/a.md", "# A\n\n[B](b.md)\n")
    write(repository_root, "docs/architecture/b.md", "# B\n")
    base_sha = commit(repository_root, "base")
    (repository_root / "docs/architecture/b.md").unlink()
    head_sha = commit(repository_root, "delete target")
    repository = GitRepository(repository_root)

    classification = classify_repository(repository, base_sha, head_sha)
    report = validate_public_docs(repository, classification)

    assert classification.profile == DOCS_ONLY
    assert report["result"] == "FAIL"
    assert report["issues"][0]["target"] == "b.md"


def test_docs_validator_allows_unchanged_preexisting_link_debt(
    repository_root: Path,
) -> None:
    write(
        repository_root,
        "docs/architecture/a.md",
        "# A\n\n[Historical debt](missing.md)\n",
    )
    write(repository_root, "docs/architecture/b.md", "# B\n")
    base_sha = commit(repository_root, "base")
    write(repository_root, "docs/architecture/b.md", "# B\n\nClarified.\n")
    head_sha = commit(repository_root, "unrelated docs")
    repository = GitRepository(repository_root)

    report = validate_public_docs(
        repository, classify_repository(repository, base_sha, head_sha)
    )

    assert report["result"] == "PASS"
    assert report["checks"][0]["base_issue_count"] == 1
    assert report["checks"][0]["head_issue_count"] == 1


@pytest.mark.parametrize(
    ("target", "expected_message"),
    (
        ("../../../../outside.md", "escapes the repository root"),
        (
            "../governance/change-impact-matrix.md",
            "non-public internal documentation",
        ),
        ("/absolute.md", "absolute links"),
        ("javascript:alert(1)", "unsupported link scheme"),
    ),
)
def test_docs_validator_rejects_unsafe_new_targets(
    repository_root: Path, target: str, expected_message: str
) -> None:
    write(repository_root, "docs/architecture/a.md", "# A\n")
    base_sha = commit(repository_root, "base")
    write(repository_root, "docs/architecture/a.md", f"# A\n\n[Unsafe]({target})\n")
    head_sha = commit(repository_root, "unsafe docs")
    repository = GitRepository(repository_root)

    report = validate_public_docs(
        repository, classify_repository(repository, base_sha, head_sha)
    )

    assert report["result"] == "FAIL"
    assert expected_message in report["issues"][0]["message"]


def test_docs_validator_rejects_new_unclosed_fence(repository_root: Path) -> None:
    write(repository_root, "docs/architecture/a.md", "# A\n")
    base_sha = commit(repository_root, "base")
    write(repository_root, "docs/architecture/a.md", "# A\n\n```text\nopen\n")
    head_sha = commit(repository_root, "unclosed fence")
    repository = GitRepository(repository_root)

    report = validate_public_docs(
        repository, classify_repository(repository, base_sha, head_sha)
    )

    assert report["result"] == "FAIL"
    assert report["issues"][0]["check_id"] == "PUBLIC-DOC-FENCE"


@pytest.mark.parametrize(
    "evidence_line",
    (
        "Provider run 12345678 completed successfully.",
        "artifact id 87654321 was retained.",
        f"sha256: {'a' * 64}",
        f"implementation {'b' * 40}",
        f"closure {'c' * 40}",
    ),
)
def test_docs_validator_rejects_new_public_readme_evidence(
    repository_root: Path, evidence_line: str
) -> None:
    write(repository_root, "README.md", "# Public\n")
    base_sha = commit(repository_root, "base")
    write(repository_root, "README.md", f"# Public\n\n{evidence_line}\n")
    head_sha = commit(repository_root, "duplicate evidence")
    repository = GitRepository(repository_root)

    report = validate_public_docs(
        repository, classify_repository(repository, base_sha, head_sha)
    )

    assert report["result"] == "FAIL"
    assert report["issues"][0]["check_id"] == "PUBLIC-DOC-EVIDENCE"


def test_docs_validator_allows_unchanged_public_readme_evidence_debt(
    repository_root: Path,
) -> None:
    write(repository_root, "README.md", "# Public\n\nProvider run 12345678 passed.\n")
    write(repository_root, "docs/README.md", "# Docs\n")
    base_sha = commit(repository_root, "base")
    write(repository_root, "docs/README.md", "# Docs\n\nClarified navigation.\n")
    head_sha = commit(repository_root, "ordinary docs")
    repository = GitRepository(repository_root)

    report = validate_public_docs(
        repository, classify_repository(repository, base_sha, head_sha)
    )

    assert report["result"] == "PASS"
    assert report["issues"] == []


def test_invalid_base_and_empty_range_fail_closed_to_full(
    repository_root: Path,
) -> None:
    write(repository_root, "docs/architecture/a.md", "# A\n")
    head_sha = commit(repository_root, "base")
    repository = GitRepository(repository_root)

    assert classify_repository(repository, "HEAD", head_sha).profile == FULL
    assert classify_repository(repository, "0" * 40, head_sha).profile == FULL
    assert classify_repository(repository, head_sha, head_sha).profile == FULL


def test_rename_from_public_to_internal_forces_full(repository_root: Path) -> None:
    write(repository_root, "docs/architecture/a.md", "# A\n")
    base_sha = commit(repository_root, "base")
    (repository_root / "docs/tasks").mkdir(parents=True)
    git(
        repository_root,
        "mv",
        "docs/architecture/a.md",
        "docs/tasks/a.md",
    )
    head_sha = commit(repository_root, "move internal")

    classification = classify_repository(
        GitRepository(repository_root), base_sha, head_sha
    )

    assert classification.profile == FULL
    assert "docs/tasks/a.md" in classification.reason


def test_cli_writes_machine_report_and_github_output(repository_root: Path) -> None:
    write(repository_root, "docs/architecture/a.md", "# A\n")
    base_sha = commit(repository_root, "base")
    write(repository_root, "docs/architecture/a.md", "# A\n\nChanged.\n")
    head_sha = commit(repository_root, "docs")
    report_path = repository_root / "build/profile.json"
    output_path = repository_root / "github-output.txt"

    exit_code = main(
        (
            "--root",
            str(repository_root),
            "classify",
            "--base",
            base_sha,
            "--head",
            head_sha,
            "--report",
            str(report_path),
            "--github-output",
            str(output_path),
        )
    )
    payload = json.loads(report_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert payload["schema_version"] == "ci-validation-profile.v1"
    assert payload["profile"] == DOCS_ONLY
    assert payload["issues"] == []
    assert output_path.read_text(encoding="utf-8") == "profile=DOCS_ONLY\n"
