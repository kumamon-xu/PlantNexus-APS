"""TEST-TRACEABILITY-VALIDATOR unit tests."""

from __future__ import annotations

import re
import unittest
from unittest.mock import Mock

from scripts.check_docs import (
    ImpactRule,
    RepositoryValidator,
    ROOT_ID_RE,
    duplicate_id_issues,
    evaluate_impact_coverage,
    expand_numeric_ranges,
    expand_task_ranges,
    missing_task_fields,
    namespace_separation_issues,
    parse_markdown_tables,
    unknown_reference_issues,
)


TEST_ID = "TEST-TRACEABILITY-VALIDATOR"


class TraceabilityValidatorTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
