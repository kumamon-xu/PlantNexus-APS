"""TEST-TRACEABILITY-VALIDATOR unit tests."""

from __future__ import annotations

import re
import unittest
from pathlib import Path
from unittest.mock import Mock

from scripts.check_docs import (
    ImpactRule,
    PHASE_PLAN_MEMBER_ROLE,
    PHASE_PLANNING_OWNER_ROLE,
    RepositoryValidator,
    ROOT_ID_RE,
    TaskDiscoveryError,
    duplicate_id_issues,
    evaluate_impact_coverage,
    expand_numeric_ranges,
    expand_task_ranges,
    missing_task_fields,
    namespace_separation_issues,
    normalize_repo_path,
    parse_markdown_tables,
    select_changed_task_path,
    task_phase_policy_issue,
    unknown_reference_issues,
)


TEST_ID = "TEST-TRACEABILITY-VALIDATOR"
PHASE_GOVERNANCE_TEST_ID = "TEST-PHASE-GOVERNANCE-001"


class TraceabilityValidatorTests(unittest.TestCase):
    def test_repository_path_normalization_preserves_hidden_directories(self) -> None:
        self.assertEqual(
            normalize_repo_path(".github/workflows/ci.yml"),
            ".github/workflows/ci.yml",
        )
        self.assertEqual(
            normalize_repo_path("./docs/tasks/P1/TASK-P1-01-phase-governance-and-ci-handoff.md"),
            "docs/tasks/P1/TASK-P1-01-phase-governance-and-ci-handoff.md",
        )

    def test_registry_table_parse(self) -> None:
        text = """
| ID | ID status | Requirement |
|---|---|---|
| REQ-001 | ALLOCATED | Input |
| REQ-002 | RETIRED | Legacy |
"""

        tables = parse_markdown_tables(text)

        self.assertEqual(len(tables), 1)
        self.assertEqual(tables[0][0]["ID"], "REQ-001")
        self.assertEqual(tables[0][1]["ID status"], "RETIRED")

    def test_duplicate_registry_id_is_rejected(self) -> None:
        issues = duplicate_id_issues(
            (("REQ-001", "first.md"), ("REQ-001", "second.md"))
        )

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].check_id, "REGISTRY-ID-UNIQUE")
        self.assertIn("duplicate definition", issues[0].message)

    def test_broken_root_reference_is_rejected(self) -> None:
        unknown_id = "REQ-" + "999"
        issues = unknown_reference_issues(
            {"example.md": f"Requirement: {unknown_id}"},
            {"REQ-001"},
            ROOT_ID_RE,
        )

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].check_id, "REFERENCE-VALID")
        self.assertIn(unknown_id, issues[0].message)

    def test_missing_document_impact_fields_are_rejected(self) -> None:
        text = "Goal: incomplete task\nDocumentation impact: required\n"

        missing = missing_task_fields(text)

        self.assertIn("Documents to update", missing)
        self.assertIn("Traceability updates", missing)
        self.assertIn("Change-impact matrix rows reviewed", missing)

    def test_diff_impact_mismatch_is_rejected(self) -> None:
        rules = (
            ImpactRule(
                "IMPACT-DOCS",
                ("docs/**",),
                ("docs/governance/document-inventory.md",),
            ),
        )

        coverage = evaluate_impact_coverage(
            ("docs/example.md",),
            rules,
            declared_rule_ids=set(),
            declared_docs=set(),
        )

        self.assertEqual(coverage.matched_rule_ids, ("IMPACT-DOCS",))
        self.assertEqual(len(coverage.issues), 2)
        self.assertTrue(all(issue.check_id == "DIFF-IMPACT" for issue in coverage.issues))

    def test_diff_base_recovers_committed_paths_in_clean_tree(self) -> None:
        diff_base = "a" * 40
        validator = object.__new__(RepositoryValidator)
        validator.diff_source_counts = {}
        validator.git_output = Mock(
            side_effect=(
                "docs/governance/traceability-rules.md\nscripts/check_docs.py\n",
                "",
            )
        )

        paths = validator.git_changed_paths(diff_base)

        self.assertEqual(
            paths,
            ["docs/governance/traceability-rules.md", "scripts/check_docs.py"],
        )
        self.assertEqual(
            validator.diff_source_counts,
            {"committed_range": 2, "working_tree": 0},
        )
        validator.git_output.assert_any_call(
            "diff",
            "--name-only",
            "--diff-filter=ACDMRTUXB",
            f"{diff_base}..HEAD",
            "--",
        )

    def test_prod_open_and_sim_assumption_mixing_is_rejected(self) -> None:
        concrete_sim_id = "SIM-" + "ASSUMPTION-001"
        concrete_open_id = "OPEN-" + "001"

        issues = namespace_separation_issues(
            f"Production row incorrectly uses {concrete_sim_id}",
            f"Simulation row incorrectly uses {concrete_open_id}",
        )

        self.assertEqual(len(issues), 2)
        self.assertTrue(
            all(issue.check_id == "PROD-SIM-SEPARATION" for issue in issues)
        )

    def test_short_and_full_ranges_expand(self) -> None:
        requirements = expand_numeric_ranges("REQ-001～REQ-003", "REQ-", 3)
        opens = expand_numeric_ranges("OPEN-001～003", "OPEN-", 3)

        self.assertEqual(requirements, {"REQ-001", "REQ-002", "REQ-003"})
        self.assertEqual(opens, {"OPEN-001", "OPEN-002", "OPEN-003"})
        self.assertIsNotNone(re.fullmatch(r"TEST-[A-Z0-9-]+", TEST_ID))

    def test_task_ranges_expand_for_any_phase(self) -> None:
        tasks = expand_task_ranges(
            "TASK-P0-09, TASK-P1-01～03, TASK-P1-04～TASK-P1-05"
        )

        self.assertEqual(
            tasks,
            {
                "TASK-P0-09",
                "TASK-P1-01",
                "TASK-P1-02",
                "TASK-P1-03",
                "TASK-P1-04",
                "TASK-P1-05",
            },
        )

    def test_phase_policy_accepts_current_and_terminal_history(self) -> None:
        self.assertIsNone(
            task_phase_policy_issue("TASK-P0-10", "P0", "P0", "P1", "done")
        )
        self.assertIsNone(
            task_phase_policy_issue("TASK-P1-01", "P1", "P1", "P1", "in_progress")
        )
        self.assertIsNotNone(
            re.fullmatch(r"TEST-[A-Z0-9-]+", PHASE_GOVERNANCE_TEST_ID)
        )

    def test_phase_policy_rejects_history_future_and_alignment_errors(self) -> None:
        historical = task_phase_policy_issue(
            "TASK-P0-10", "P0", "P0", "P1", "ready"
        )
        future_task_id = "TASK-" + "P2-01"
        future = task_phase_policy_issue(
            future_task_id, "P2", "P2", "P1", "planned"
        )
        misaligned = task_phase_policy_issue(
            "TASK-P1-01", "P1", "P0", "P1", "in_progress"
        )

        self.assertIsNotNone(historical)
        self.assertIn("historical", historical[0] if historical else "")
        self.assertIsNotNone(future)
        self.assertIn("future", future[0] if future else "")
        self.assertIsNotNone(misaligned)
        self.assertIn(
            "do not identify the same phase", misaligned[0] if misaligned else ""
        )

    def test_changed_task_selection_is_current_phase_and_unique(self) -> None:
        selected = select_changed_task_path(
            (
                "README.md",
                "docs/tasks/P1/TASK-P1-01-phase-governance-and-ci-handoff.md",
                "docs/quality/ci-gates-and-definition-of-done.md",
            ),
            "P1",
        )

        self.assertEqual(
            selected,
            "docs/tasks/P1/TASK-P1-01-phase-governance-and-ci-handoff.md",
        )
        self.assertIsNone(select_changed_task_path(("README.md",), "P1"))

    def test_changed_task_selection_rejects_stale_or_multiple_cards(self) -> None:
        with self.assertRaisesRegex(TaskDiscoveryError, "outside current P1"):
            select_changed_task_path(
                (
                    "docs/tasks/P0/TASK-P0-10-ci-provider-evidence-remediation.md",
                ),
                "P1",
            )

        with self.assertRaisesRegex(TaskDiscoveryError, "multiple current P1"):
            select_changed_task_path(
                (
                    "docs/tasks/P1/TASK-P1-01-phase-governance-and-ci-handoff.md",
                    "docs/tasks/P1/TASK-P1-02-canonical-import-contracts.md",
                ),
                "P1",
            )

    def test_phase_planning_batch_selects_one_explicit_owner(self) -> None:
        owner = "docs/tasks/P2/TASK-P2-00-phase-transition-and-task-planning.md"
        first = "docs/tasks/P2/TASK-P2-01-planning-problem-v2.md"
        second = "docs/tasks/P2/TASK-P2-02-planning-machine-contracts.md"
        texts = {
            owner: (
                "---\ndoc_id: TASK-P2-00\nstatus: in_progress\n---\n"
                f"Task batch role: {PHASE_PLANNING_OWNER_ROLE}\n"
                f"Diff base: {'a' * 40}\n"
            ),
            first: (
                "---\ndoc_id: TASK-P2-01\nstatus: planned\n---\n"
                f"Task batch role: {PHASE_PLAN_MEMBER_ROLE}\n"
                "Diff base: set only when the Task enters in_progress\n"
            ),
            second: (
                "---\ndoc_id: TASK-P2-02\nstatus: ready\n---\n"
                f"Task batch role: {PHASE_PLAN_MEMBER_ROLE}\n"
                "Diff base: set only when the Task enters in_progress\n"
            ),
        }

        selected = select_changed_task_path(
            texts,
            "P2",
            added_paths=texts,
            task_texts=texts,
        )

        self.assertEqual(selected, owner)

    def test_phase_planning_batch_rejects_existing_or_active_members(self) -> None:
        owner = "docs/tasks/P2/TASK-P2-00-phase-transition-and-task-planning.md"
        member = "docs/tasks/P2/TASK-P2-01-planning-problem-v2.md"
        owner_text = (
            "---\ndoc_id: TASK-P2-00\nstatus: done\n---\n"
            f"Task batch role: {PHASE_PLANNING_OWNER_ROLE}\n"
            f"Diff base: {'a' * 40}\n"
        )
        member_text = (
            "---\ndoc_id: TASK-P2-01\nstatus: in_progress\n---\n"
            f"Task batch role: {PHASE_PLAN_MEMBER_ROLE}\n"
            "Diff base: set only when the Task enters in_progress\n"
        )

        with self.assertRaisesRegex(TaskDiscoveryError, "newly added"):
            select_changed_task_path(
                (owner, member),
                "P2",
                added_paths=(owner,),
                task_texts={owner: owner_text, member: member_text},
            )
        with self.assertRaisesRegex(TaskDiscoveryError, "planned or ready"):
            select_changed_task_path(
                (owner, member),
                "P2",
                added_paths=(owner, member),
                task_texts={owner: owner_text, member: member_text},
            )

    def test_repository_discovery_uses_an_immutable_event_range(self) -> None:
        change_base = "a" * 40
        task_path = "docs/tasks/P1/TASK-P1-01-phase-governance-and-ci-handoff.md"
        validator = object.__new__(RepositoryValidator)
        validator.root = Path(__file__).resolve().parents[3]
        validator.git_output = Mock(
            side_effect=(change_base, "", f"{task_path}\n", f"{task_path}\n")
        )

        selected = validator.discover_changed_task_path(change_base, "P1")

        self.assertEqual(selected, task_path)
        self.assertEqual(validator.task_discovery_base, change_base)
        validator.git_output.assert_any_call(
            "diff",
            "--name-only",
            "--diff-filter=ACDMRTUXB",
            f"{change_base}..HEAD",
            "--",
            "docs/tasks",
        )
        validator.git_output.assert_any_call(
            "diff",
            "--name-only",
            "--diff-filter=A",
            f"{change_base}..HEAD",
            "--",
            "docs/tasks",
        )

        with self.assertRaisesRegex(TaskDiscoveryError, "40-character"):
            validator.discover_changed_task_path("HEAD", "P1")

if __name__ == "__main__":
    unittest.main()
