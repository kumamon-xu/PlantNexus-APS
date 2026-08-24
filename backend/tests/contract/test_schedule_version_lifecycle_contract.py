"""TASK-P3-04 generated ScheduleVersion and AuditEvent contract tests."""

from __future__ import annotations

import ast
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator, FormatChecker
import pytest
from referencing import Registry, Resource

from app.application.schedule_version_lifecycle_check import (
    lifecycle_context,
    load_fixed_validated_output,
)
from app.domain.schedule_version import (
    ScheduleVersionLifecycleError,
    ScheduleVersionLifecycleFailure,
    ValidatedPlanningOutput,
    build_reviewable_schedule_documents,
)
from app.domain.state_machines.schedule_version import immutable_schedule_projection
from app.domain.workspace_contracts import (
    canonical_workspace_bytes,
    require_workspace_document,
)
from app.planning.reporting.kpi import build_kpi_v2
from app.simulation.scenarios.p2_correctness import (
    CorrectnessReplay,
    execute_correctness_case,
    load_correctness_cases,
    verify_correctness_replay,
)


ROOT = Path(__file__).resolve().parents[3]
SCHEMA_ROOT = ROOT / "schemas" / "json"
TEST_LIFECYCLE_ID = "TEST-SCHEDULE-VERSION-LIFECYCLE-001"
TEST_SIM_ISOLATION_ID = "TEST-SIM-ISOLATION"
TEST_STATE_ID = "TEST-STATE-TRANSITION-001"


@pytest.fixture(scope="module")
def validated_bundle() -> tuple[ValidatedPlanningOutput, CorrectnessReplay]:
    return load_fixed_validated_output(ROOT)


@pytest.fixture(scope="module")
def validated_output(
    validated_bundle: tuple[ValidatedPlanningOutput, CorrectnessReplay],
) -> ValidatedPlanningOutput:
    return validated_bundle[0]


@pytest.fixture(scope="module")
def locked_output() -> ValidatedPlanningOutput:
    case = load_correctness_cases(ROOT)[-1]
    replay = execute_correctness_case(case, root=ROOT)
    verify_correctness_replay(replay)
    assert replay.problem["operation_locks"]
    kpi = build_kpi_v2(
        snapshot=replay.snapshot_document,
        problem=replay.problem,
        solution=replay.solution,
        solver_report=replay.solver_report,
        validation_report=replay.validation_report,
        import_quality_report=replay.quality_report,
    )
    return ValidatedPlanningOutput(
        snapshot=replay.snapshot_document,
        problem=replay.problem,
        solution=replay.solution,
        solver_report=replay.solver_report,
        validation_report=replay.validation_report,
        import_quality_report=replay.quality_report,
        kpi=kpi.document,
    )


def _json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _validator(name: str) -> Draft202012Validator:
    schemas: dict[str, dict[str, Any]] = {}
    resources: list[tuple[str, Resource[Any]]] = []
    for path in sorted(SCHEMA_ROOT.glob("*.json")):
        schema = _json(path)
        schemas[path.name] = schema
        resources.append((cast(str, schema["$id"]), Resource.from_contents(schema)))
    registry = Registry().with_resources(resources)
    return Draft202012Validator(
        schemas[name], registry=registry, format_checker=FormatChecker()
    )


def test_generated_draft_ready_and_audit_validate_against_frozen_p3_schemas(
    validated_bundle: tuple[ValidatedPlanningOutput, CorrectnessReplay],
) -> None:
    output, replay = validated_bundle
    documents = build_reviewable_schedule_documents(
        output, lifecycle_context(), data_plane="SIMULATION"
    )
    schedule_validator = _validator("schedule-version.schema.json")
    audit_validator = _validator("audit-event.schema.json")

    schedule_validator.validate(documents.draft)
    schedule_validator.validate(documents.ready_for_review)
    audit_validator.validate(documents.audit_event)
    assert require_workspace_document(documents.draft) == "schedule-version.v1"
    assert (
        require_workspace_document(documents.ready_for_review) == "schedule-version.v1"
    )
    assert require_workspace_document(documents.audit_event) == "audit-event.v1"

    expected_provenance = replay.snapshot_document["synthetic_provenance"]
    assert documents.draft["synthetic_provenance"] == expected_provenance
    assert documents.audit_event["synthetic_provenance"] == expected_provenance
    lineage = cast(dict[str, object], documents.draft["lineage"])
    assert lineage["planning_run_id"] == replay.solver_report["planning_run_id"]
    assert (
        lineage["code_commit"]
        == cast(dict[str, object], replay.solver_report["provenance"])["code_commit"]
    )
    assert (
        lineage["validation_report"]
        == cast(dict[str, object], documents.draft["validation"])["validation_report"]
    )
    assert TEST_LIFECYCLE_ID == "TEST-SCHEDULE-VERSION-LIFECYCLE-001"
    assert TEST_SIM_ISOLATION_ID == "TEST-SIM-ISOLATION"


def test_generated_carriers_contain_no_approval_publication_export_or_raw_secret(
    validated_output: ValidatedPlanningOutput,
) -> None:
    documents = build_reviewable_schedule_documents(
        validated_output, lifecycle_context("b"), data_plane="SIMULATION"
    )
    rendered = json.dumps(
        {
            "draft": documents.draft,
            "ready": documents.ready_for_review,
            "audit": documents.audit_event,
        },
        sort_keys=True,
    ).lower()

    assert documents.draft["decision"] is None
    assert documents.draft["publication"] is None
    assert documents.ready_for_review["decision"] is None
    assert documents.ready_for_review["publication"] is None
    assert documents.audit_event["export_job_id"] is None
    assert '"authorization"' not in rendered
    assert '"password"' not in rendered
    assert '"secret"' not in rendered
    assert '"token"' not in rendered


def test_builder_is_deterministic_and_does_not_mutate_validated_inputs(
    validated_output: ValidatedPlanningOutput,
) -> None:
    before = tuple(
        canonical_workspace_bytes(document)
        for document in (
            validated_output.snapshot,
            validated_output.problem,
            validated_output.solution,
            validated_output.solver_report,
            validated_output.validation_report,
            validated_output.import_quality_report,
            validated_output.kpi,
        )
    )
    context = lifecycle_context("c")
    first = build_reviewable_schedule_documents(
        validated_output, context, data_plane="SIMULATION"
    )
    second = build_reviewable_schedule_documents(
        validated_output, context, data_plane="SIMULATION"
    )

    assert first == second
    for changed_context in (
        replace(context, auth_policy_version="upstream-auth-context.v2"),
        replace(context, occurred_at_utc="2026-08-24T06:00:01Z"),
        replace(context, correlation_id="correlation-p3-04-changed"),
    ):
        changed = build_reviewable_schedule_documents(
            validated_output, changed_context, data_plane="SIMULATION"
        )
        assert changed.request_fingerprint != first.request_fingerprint
    assert immutable_schedule_projection(first.draft) == immutable_schedule_projection(
        first.ready_for_review
    )
    assert first.draft["allowed_actions"] == ["view", "edit", "lock"]
    assert first.ready_for_review["allowed_actions"] == [
        "view",
        "approve",
        "reject",
    ]
    assert first.audit_event["result"] == {
        "outcome": "SUCCEEDED",
        "replayed": False,
        "retryable": False,
        "error": None,
    }
    after = tuple(
        canonical_workspace_bytes(document)
        for document in (
            validated_output.snapshot,
            validated_output.problem,
            validated_output.solution,
            validated_output.solver_report,
            validated_output.validation_report,
            validated_output.import_quality_report,
            validated_output.kpi,
        )
    )
    assert after == before
    assert TEST_STATE_ID == "TEST-STATE-TRANSITION-001"


def test_builder_preserves_validated_problem_locks_as_schedule_content(
    locked_output: ValidatedPlanningOutput,
) -> None:
    documents = build_reviewable_schedule_documents(
        locked_output,
        lifecycle_context("d", correlation_id="correlation-p3-04-lock"),
        data_plane="SIMULATION",
    )
    problem_locks = cast(
        list[dict[str, object]], locked_output.problem["operation_locks"]
    )
    content = cast(dict[str, object], documents.draft["content"])
    schedule_locks = cast(list[dict[str, object]], content["locks"])

    assert len(schedule_locks) == len(problem_locks)
    assert schedule_locks[0]["lock_id"] == problem_locks[0]["lock_id"]
    assert schedule_locks[0]["lock_type"] == "HARD"
    assert schedule_locks[0]["resource_id"] == problem_locks[0]["resource_id"]
    assert schedule_locks[0]["start_at_utc"] == problem_locks[0]["start_at_utc"]
    assert schedule_locks[0]["end_at_utc"] == problem_locks[0]["end_at_utc"]


def test_builder_rejects_non_completed_mixed_failed_and_production_synthetic(
    validated_output: ValidatedPlanningOutput,
) -> None:
    with pytest.raises(ScheduleVersionLifecycleError) as state_error:
        build_reviewable_schedule_documents(
            validated_output,
            replace(lifecycle_context("e"), planning_run_state="VERIFYING"),
            data_plane="SIMULATION",
        )
    assert (
        state_error.value.reason
        is ScheduleVersionLifecycleFailure.PLANNING_RUN_NOT_COMPLETED
    )

    mixed_problem = cast(dict[str, object], deepcopy(validated_output.problem))
    mixed_problem["snapshot_id"] = "planning-snapshot-mixed"
    with pytest.raises(ScheduleVersionLifecycleError) as mixed_error:
        build_reviewable_schedule_documents(
            replace(validated_output, problem=mixed_problem),
            lifecycle_context("f"),
            data_plane="SIMULATION",
        )
    assert mixed_error.value.reason is ScheduleVersionLifecycleFailure.MIXED_LINEAGE

    failed_validation = cast(
        dict[str, object], deepcopy(validated_output.validation_report)
    )
    failed_validation.update(
        {"status": "FAIL", "hard_violation_count": 1, "violations": []}
    )
    with pytest.raises(ScheduleVersionLifecycleError) as validation_error:
        build_reviewable_schedule_documents(
            replace(validated_output, validation_report=failed_validation),
            lifecycle_context("1"),
            data_plane="SIMULATION",
        )
    assert (
        validation_error.value.reason
        is ScheduleVersionLifecycleFailure.VALIDATION_FAILED
    )

    with pytest.raises(ScheduleVersionLifecycleError) as plane_error:
        build_reviewable_schedule_documents(
            validated_output,
            replace(lifecycle_context("2"), environment="PRODUCTION"),
            data_plane="PRODUCTION",
        )
    assert (
        plane_error.value.reason is ScheduleVersionLifecycleFailure.DATA_PLANE_MISMATCH
    )

    invalid_instant = replace(
        lifecycle_context("3"), occurred_at_utc=cast(Any, 20260824)
    )
    with pytest.raises(ScheduleVersionLifecycleError) as instant_error:
        build_reviewable_schedule_documents(
            validated_output, invalid_instant, data_plane="SIMULATION"
        )
    assert instant_error.value.reason is ScheduleVersionLifecycleFailure.INVALID_INPUT


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_domain_and_service_do_not_import_solver_or_reverse_dependencies() -> None:
    domain_path = ROOT / "backend" / "app" / "domain" / "schedule_version.py"
    service_path = ROOT / "backend" / "app" / "application" / "schedule_versions.py"
    domain_imports = _imports(domain_path)
    service_imports = _imports(service_path)

    assert not any(
        module.startswith(("app.infrastructure", "app.planning", "app.simulation"))
        for module in domain_imports
    )
    assert not any(
        module.startswith(
            (
                "app.planning.backends",
                "app.planning.strategies",
                "app.simulation",
            )
        )
        for module in service_imports
    )
    assert ".solve(" not in service_path.read_text(encoding="utf-8")
