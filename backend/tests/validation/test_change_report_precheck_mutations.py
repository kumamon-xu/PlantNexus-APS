"""TEST-VALIDATOR-MUTATION independent ChangeReport recomputation evidence."""

from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path
from typing import cast

import pytest

from app.domain.execution_contracts import change_report_fingerprint
from app.planning.reporting.stability_change_report_check import (
    StabilityChangeReportFixture,
    build_fixture_change_report,
    build_stability_change_report_fixture,
)
from app.planning.validation.change_report_precheck import (
    ChangeReportPrecheckInputError,
    validate_change_report,
)


ROOT = Path(__file__).resolve().parents[3]
TEST_ID = "TEST-VALIDATOR-MUTATION"


@pytest.fixture(scope="module")
def fixture() -> StabilityChangeReportFixture:
    return build_stability_change_report_fixture(ROOT)


def _validate(
    fixture: StabilityChangeReportFixture, report: dict[str, object]
) -> dict[str, object]:
    return validate_change_report(
        context=fixture.context,
        base_assignments=fixture.base_assignments,
        new_assignments=fixture.new_assignments,
        active_operation_ids=fixture.active_operation_ids,
        active_soft_locks=fixture.active_soft_locks,
        removed_by_fact=fixture.removed_by_fact,
        reasons_by_operation=fixture.reasons_by_operation,
        before_kpi=fixture.before_kpi,
        after_kpi=fixture.after_kpi,
        report=report,
    )


def _rehash(report: dict[str, object]) -> None:
    fingerprint = change_report_fingerprint(report)
    report["report_fingerprint"] = fingerprint
    report["report_id"] = "change-report-" + fingerprint.removeprefix("sha256:")


@pytest.mark.parametrize(
    ("mutation", "expected_field"),
    (
        ("stability", "stability"),
        ("operation-drop", "operations"),
        ("classification", "operations"),
        ("removed-fact", "operations"),
        ("after-kpi", "after_kpi"),
        ("fingerprint", "report_fingerprint"),
    ),
)
def test_each_report_mutation_is_rejected_independently(
    fixture: StabilityChangeReportFixture,
    mutation: str,
    expected_field: str,
) -> None:
    report = cast(dict[str, object], deepcopy(build_fixture_change_report(fixture).document))
    if mutation == "stability":
        cast(dict[str, object], report["stability"])["resource_changes"] = 0
        _rehash(report)
    elif mutation == "operation-drop":
        cast(list[dict[str, object]], report["operations"]).pop()
        report["operation_universe_count"] = 3
        _rehash(report)
    elif mutation == "classification":
        cast(list[dict[str, object]], report["operations"])[1]["classification"] = (
            "UNCHANGED"
        )
        _rehash(report)
    elif mutation == "removed-fact":
        removed = cast(list[dict[str, object]], report["operations"])[2]
        cast(list[dict[str, object]], removed["reasons"])[0]["evidence_refs"] = [
            {
                "document_version": "execution-fact.v1",
                "artifact_id": "execution-fact-wrong-001",
                "fingerprint": "sha256:" + "e" * 64,
            }
        ]
        _rehash(report)
    elif mutation == "after-kpi":
        cast(dict[str, object], report["after_kpi"])["fingerprint"] = (
            "sha256:" + "f" * 64
        )
        _rehash(report)
    else:
        report["report_fingerprint"] = "sha256:" + "0" * 64

    first = _validate(fixture, report)
    replay = _validate(fixture, cast(dict[str, object], deepcopy(report)))
    assert first == replay
    assert first["status"] == "FAIL"
    assert cast(int, first["hard_violation_count"]) >= 1
    assert expected_field in {
        violation["field"]
        for violation in cast(list[dict[str, object]], first["violations"])
    }


def test_invalid_authoritative_universe_fails_before_report_compare(
    fixture: StabilityChangeReportFixture,
) -> None:
    report = build_fixture_change_report(fixture).document
    with pytest.raises(ChangeReportPrecheckInputError) as rejected:
        validate_change_report(
            context=fixture.context,
            base_assignments=(
                fixture.base_assignments[0],
                deepcopy(fixture.base_assignments[0]),
            ),
            new_assignments=fixture.new_assignments,
            active_operation_ids=fixture.active_operation_ids,
            active_soft_locks=fixture.active_soft_locks,
            removed_by_fact=fixture.removed_by_fact,
            reasons_by_operation=fixture.reasons_by_operation,
            before_kpi=fixture.before_kpi,
            after_kpi=fixture.after_kpi,
            report=report,
        )
    assert rejected.value.reason == "DUPLICATE_OPERATION"


def test_precheck_has_no_builder_solver_or_formal_validator_import() -> None:
    source_path = (
        ROOT / "backend/app/planning/validation/change_report_precheck.py"
    )
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.add(node.module)
    assert all(not name.startswith("app.planning.reporting") for name in imported)
    assert all(not name.startswith("app.planning.backends") for name in imported)
    assert "app.planning.validation.problem_schedule_validator" not in imported
    assert "ortools" not in imported
    assert TEST_ID == "TEST-VALIDATOR-MUTATION"
