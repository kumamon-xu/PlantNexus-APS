"""TEST-VALIDATOR-MUTATION independent freeze precheck evidence."""

from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path
from typing import cast

import pytest

from app.domain.workspace_contracts import workspace_fingerprint
from app.planning.problem.freeze_projection import project_effective_locks
from app.planning.problem.freeze_window_check import (
    FreezeWindowFixture,
    build_freeze_window_fixture,
    move_base_assignment,
    rehash_problem_v2,
)
from app.planning.validation.freeze_window_precheck import (
    FreezePrecheckInputError,
    validate_freeze_window_projection,
)


ROOT = Path(__file__).resolve().parents[3]
TEST_ID = "TEST-VALIDATOR-MUTATION"


@pytest.fixture(scope="module")
def primary() -> FreezeWindowFixture:
    return build_freeze_window_fixture(ROOT)


@pytest.fixture(scope="module")
def completed() -> FreezeWindowFixture:
    return build_freeze_window_fixture(ROOT, completed=True)


def _projection(fixture: FreezeWindowFixture) -> dict[str, object]:
    return project_effective_locks(
        snapshot=fixture.snapshot,
        problem=fixture.problem,
        base_schedule=fixture.base_schedule,
        policy=fixture.policy,
    ).document


@pytest.mark.parametrize(
    ("mutation", "expected_check"),
    (
        ("running-resource", "C-007"),
        ("hard-end", "C-008"),
        ("derived-resource", "C-008"),
        ("soft-drop", "FREEZE-SOFT-INPUT"),
        ("freeze-end", "FREEZE-POLICY"),
        ("fingerprint", "FREEZE-IDENTITY"),
        ("extra-root", "FREEZE-COMPLETENESS"),
    ),
)
def test_each_effective_projection_mutation_is_rejected_independently(
    primary: FreezeWindowFixture,
    mutation: str,
    expected_check: str,
) -> None:
    document = cast(dict[str, object], deepcopy(_projection(primary)))
    if mutation == "running-resource":
        cast(list[dict[str, object]], document["running_protections"])[0][
            "resource_id"
        ] = "RESOURCE-MUTATED"
    elif mutation == "hard-end":
        cast(list[dict[str, object]], document["explicit_hard_locks"])[0][
            "end_at_utc"
        ] = "2026-08-19T00:09:00Z"
    elif mutation == "derived-resource":
        cast(list[dict[str, object]], document["freeze_derived_hard_locks"])[0][
            "resource_id"
        ] = "RESOURCE-MUTATED"
    elif mutation == "soft-drop":
        document["soft_locks"] = []
    elif mutation == "freeze-end":
        cast(dict[str, object], document["freeze_resolution"])[
            "effective_until_utc"
        ] = "2026-08-19T00:16:00Z"
    elif mutation == "fingerprint":
        document["projection_fingerprint"] = "sha256:" + "0" * 64
    else:
        document["unexpected"] = True

    first = validate_freeze_window_projection(
        snapshot=primary.snapshot,
        problem=primary.problem,
        base_schedule=primary.base_schedule,
        policy=primary.policy,
        projection=document,
    )
    replay = validate_freeze_window_projection(
        snapshot=primary.snapshot,
        problem=primary.problem,
        base_schedule=primary.base_schedule,
        policy=primary.policy,
        projection=deepcopy(document),
    )
    assert first == replay
    assert first["status"] == "FAIL"
    assert cast(int, first["hard_violation_count"]) >= 1
    assert expected_check in {
        violation["check_id"]
        for violation in cast(list[dict[str, object]], first["violations"])
    }


def test_completed_fact_omission_is_a_c007_violation(
    completed: FreezeWindowFixture,
) -> None:
    document = cast(dict[str, object], deepcopy(_projection(completed)))
    document["completed_protections"] = []
    report = validate_freeze_window_projection(
        snapshot=completed.snapshot,
        problem=completed.problem,
        base_schedule=completed.base_schedule,
        policy=completed.policy,
        projection=document,
    )
    assert report["status"] == "FAIL"
    assert "C-007" in {
        violation["check_id"]
        for violation in cast(list[dict[str, object]], report["violations"])
    }


def test_duplicate_stale_and_cross_plane_authoritative_inputs_fail_before_compare(
    primary: FreezeWindowFixture,
    completed: FreezeWindowFixture,
) -> None:
    valid_projection = _projection(primary)
    duplicate = cast(dict[str, object], deepcopy(primary.base_schedule))
    duplicate_content = cast(dict[str, object], duplicate["content"])
    duplicate_assignments = cast(
        list[dict[str, object]], duplicate_content["assignments"]
    )
    duplicate_assignments.append(deepcopy(duplicate_assignments[0]))
    duplicate["content_fingerprint"] = workspace_fingerprint(duplicate_content)
    with pytest.raises(FreezePrecheckInputError) as duplicate_error:
        validate_freeze_window_projection(
            snapshot=primary.snapshot,
            problem=primary.problem,
            base_schedule=duplicate,
            policy=primary.policy,
            projection=valid_projection,
        )
    assert duplicate_error.value.reason == "DUPLICATE_OPERATION"

    stale = move_base_assignment(
        completed.base_schedule,
        operation_id=completed.second_operation_id,
        start_at_utc="2026-08-19T00:00:00Z",
    )
    with pytest.raises(FreezePrecheckInputError) as stale_error:
        validate_freeze_window_projection(
            snapshot=completed.snapshot,
            problem=completed.problem,
            base_schedule=stale,
            policy=completed.policy,
            projection=_projection(completed),
        )
    assert stale_error.value.reason == "STALE_BASE"

    cross_plane = cast(dict[str, object], deepcopy(primary.base_schedule))
    cross_plane["data_plane"] = "PRODUCTION"
    with pytest.raises(FreezePrecheckInputError) as plane_error:
        validate_freeze_window_projection(
            snapshot=primary.snapshot,
            problem=primary.problem,
            base_schedule=cross_plane,
            policy=primary.policy,
            projection=valid_projection,
        )
    assert plane_error.value.reason == "PLANE_MISMATCH"

    forged_document = cast(dict[str, object], deepcopy(completed.problem.document))
    anchors = cast(
        list[dict[str, object]],
        forged_document["historical_completion_anchors"],
    )
    assert anchors
    anchors[0]["source_record_id"] = "forged-but-schema-valid-source-record"
    with pytest.raises(FreezePrecheckInputError) as anchor_error:
        validate_freeze_window_projection(
            snapshot=completed.snapshot,
            problem=rehash_problem_v2(forged_document),
            base_schedule=completed.base_schedule,
            policy=completed.policy,
            projection=_projection(completed),
        )
    assert anchor_error.value.reason == "LINEAGE_MISMATCH"


def test_precheck_has_no_projector_solver_or_formal_validator_import() -> None:
    source_path = (
        ROOT
        / "backend/app/planning/validation/freeze_window_precheck.py"
    )
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.add(node.module)
    assert "app.planning.problem.freeze_projection" not in imported
    assert all(not name.startswith("app.planning.backends") for name in imported)
    assert "app.planning.validation.problem_schedule_validator" not in imported
    assert "ortools" not in imported
    assert TEST_ID == "TEST-VALIDATOR-MUTATION"
