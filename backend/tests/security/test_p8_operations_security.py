"""Security and redaction evidence for TASK-P8-10 operations tooling."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.p8_operations_check import main, redact_for_report

ROOT = Path(__file__).resolve().parents[3]


def test_report_redaction_removes_nested_credentials_and_urls() -> None:
    value = redact_for_report(
        {
            "database_url": "postgresql://operator:do-not-leak@database/db",
            "nested": {
                "authorization": "Bearer do-not-leak",
                "message": "redis://operator:do-not-leak@redis/0",
            },
        }
    )
    rendered = json.dumps(value)
    assert "do-not-leak" not in rendered
    assert value == {
        "database_url": "[REDACTED]",
        "nested": {
            "authorization": "[REDACTED]",
            "message": "redis://[REDACTED]@redis/0",
        },
    }


def test_failure_reports_are_stable_and_do_not_echo_private_paths(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "customer-password-do-not-leak"
    missing.mkdir()
    report_root = missing / "build" / "validation"
    reports = [report_root / f"failure-{index}.json" for index in range(4)]
    assert (
        main(
            [
                "--root",
                str(missing),
                "--contract-only",
                "--deployment-report",
                str(reports[0]),
                "--observability-report",
                str(reports[1]),
                "--recovery-report",
                str(reports[2]),
                "--runbook-report",
                str(reports[3]),
            ]
        )
        == 1
    )
    rendered = "".join(path.read_text(encoding="utf-8") for path in reports)
    assert "do-not-leak" not in rendered
    assert str(tmp_path) not in rendered
    assert "CONTRACT_UNREADABLE" in rendered
    assert "Production" not in rendered


def test_report_paths_must_be_distinct_and_inside_validation_root(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repository"
    root.mkdir()
    external = tmp_path / "outside.json"
    valid = root / "build" / "validation" / "valid.json"
    assert (
        main(
            [
                "--root",
                str(root),
                "--contract-only",
                "--deployment-report",
                str(external),
                "--observability-report",
                str(valid),
                "--recovery-report",
                str(valid),
                "--runbook-report",
                str(valid),
            ]
        )
        == 2
    )
    assert not external.exists()
    assert not valid.exists()


def test_committed_operations_assets_contain_no_secret_values() -> None:
    paths = [
        ROOT / "infra/operations/non-production-target.v1.json",
        ROOT / "infra/operations/observability-policy.v1.json",
        ROOT / "infra/operations/runtime-http-policy.v1.json",
        ROOT / "infra/operations/compose.p8-operations.yml",
    ]
    rendered = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    assert "replace-me" not in rendered
    assert "do-not-leak" not in rendered
    assert "Bearer " not in rendered
    assert "postgresql+psycopg://plantnexus:@" not in rendered
