"""TASK-P2-11 KPI v2 and SolverReport output-contract evidence."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any, cast

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from app.exporters import build_internal_export_package
from app.planning.contracts import contract_fingerprint
from app.planning.reporting import (
    ReportingContractError,
    ReportingContractErrorCode,
    build_kpi_v2,
    freeze_solver_report,
)
from app.simulation.scenarios.p2_correctness import (
    CorrectnessReplay,
    execute_correctness_case,
    load_correctness_cases,
)


ROOT = Path(__file__).resolve().parents[3]
KPI_V1_SHA256 = "be3dfbcd06e9fb7887df699c2ba0fc8bb229d603b0d55a75268a72bc2cdc9426"


@pytest.fixture(scope="module")
def replay() -> CorrectnessReplay:
    case = load_correctness_cases(ROOT)[0]
    return execute_correctness_case(case, root=ROOT)


def _schema(name: str) -> Draft202012Validator:
    document = json.loads((ROOT / "schemas" / "json" / name).read_text("utf-8"))
    return Draft202012Validator(document, format_checker=FormatChecker())


def _kpi(replay: CorrectnessReplay):  # type: ignore[no-untyped-def]
    return build_kpi_v2(
        snapshot=replay.snapshot_document,
        problem=replay.problem,
        solution=replay.solution,
        solver_report=replay.solver_report,
        validation_report=replay.validation_report,
        import_quality_report=replay.quality_report,
    )


def test_additive_kpi_and_manifest_schemas_preserve_kpi_v1_bytes() -> None:
    assert (
        hashlib.sha256(
            (ROOT / "schemas" / "json" / "kpi.schema.json").read_bytes()
        ).hexdigest()
        == KPI_V1_SHA256
    )
    for schema_name, sample_name in (
        ("kpi.v2.schema.json", "kpi.v2.synthetic.json"),
        ("export-manifest.schema.json", "export-manifest.v1.synthetic.json"),
    ):
        sample = json.loads(
            (ROOT / "schemas" / "samples" / sample_name).read_text("utf-8")
        )
        _schema(schema_name).validate(sample)


def test_solver_report_freezes_to_exact_canonical_bytes(
    replay: CorrectnessReplay,
) -> None:
    first = freeze_solver_report(
        replay.solution, replay.solver_report, replay.validation_report
    )
    second = freeze_solver_report(
        deepcopy(replay.solution),
        deepcopy(replay.solver_report),
        deepcopy(replay.validation_report),
    )
    assert first == second
    assert first.document == replay.solver_report
    assert first.fingerprint == contract_fingerprint(replay.solver_report)
    assert first.planning_run_id == replay.solver_report["planning_run_id"]


def test_kpi_recomputes_obj001_planning_and_resource_metrics(
    replay: CorrectnessReplay,
) -> None:
    immutable = _kpi(replay)
    document = immutable.document
    _schema("kpi.v2.schema.json").validate(document)

    delivery = cast(dict[str, Any], document["delivery"])
    planning = cast(dict[str, Any], document["planning"])
    solver = cast(dict[str, Any], document["solver"])
    resources = cast(list[dict[str, Any]], document["resources"])
    assert (
        delivery["priority_weighted_tardiness_seconds"]
        == replay.solution["objective_stage_results"][0]["objective_value"]
    )
    assert solver["objective_value"] == delivery["priority_weighted_tardiness_seconds"]
    assert planning["scheduled_operation_count"] == len(
        replay.problem["operation_instances"]
    )
    assert planning["unscheduled_operation_count"] == 0
    assert planning["makespan_seconds"] == max(
        assignment["end_tick"] for assignment in replay.solution["assignments"]
    ) * cast(int, replay.problem["tick_seconds"])
    assert all(
        row["utilization"] is None
        if row["available_seconds"] == 0
        else row["utilization"]
        == round(row["planned_busy_seconds"] / row["available_seconds"], 12)
        for row in resources
    )
    assert document["stability"] == {
        "status": "NOT_APPLICABLE_NO_BASE_SCHEDULE",
        "changed_operation_count": None,
        "resource_changed_count": None,
        "start_shift_seconds": None,
        "schedule_stability_ratio": None,
    }


def test_all_correctness_scenarios_emit_schema_valid_kpi_and_manifest() -> None:
    for case in load_correctness_cases(ROOT):
        replay = execute_correctness_case(case, root=ROOT)
        package = build_internal_export_package(
            snapshot=replay.snapshot_document,
            problem=replay.problem,
            solution=replay.solution,
            solver_report=replay.solver_report,
            validation_report=replay.validation_report,
            import_quality_report=replay.quality_report,
            scenario_manifest=replay.case.manifest,
        )
        _schema("kpi.v2.schema.json").validate(
            json.loads(package.read_bytes("kpi.json"))
        )
        _schema("export-manifest.schema.json").validate(package.manifest)


def test_reporting_rejects_validator_fail_and_mixed_run(
    replay: CorrectnessReplay,
) -> None:
    failed_validation = deepcopy(replay.validation_report)
    failed_validation.update(
        {
            "status": "FAIL",
            "hard_violation_count": 1,
            "violations": [
                {
                    "constraint_id": "C-001",
                    "severity": "HARD",
                    "entity_ids": [replay.solution["assignments"][0]["operation_id"]],
                    "observed_value": "tampered",
                    "expected_rule": "one assignment",
                    "message": "test-only negative",
                }
            ],
        }
    )
    with pytest.raises(ReportingContractError) as failed:
        _ = build_kpi_v2(
            snapshot=replay.snapshot_document,
            problem=replay.problem,
            solution=replay.solution,
            solver_report=replay.solver_report,
            validation_report=failed_validation,
            import_quality_report=replay.quality_report,
        )
    assert failed.value.code is ReportingContractErrorCode.VALIDATION_FAILED

    mixed_report = deepcopy(replay.solver_report)
    mixed_report["planning_run_id"] = "RUN-MIXED-P2-11"
    with pytest.raises(ReportingContractError) as mixed:
        freeze_solver_report(replay.solution, mixed_report, replay.validation_report)
    assert mixed.value.code in {
        ReportingContractErrorCode.INVALID_CONTRACT,
        ReportingContractErrorCode.MIXED_LINEAGE,
    }


def test_kpi_bytes_are_stable_and_input_documents_are_not_mutated(
    replay: CorrectnessReplay,
) -> None:
    before = json.dumps(
        {
            "snapshot": replay.snapshot_document,
            "problem": replay.problem,
            "solution": replay.solution,
            "report": replay.solver_report,
            "validation": replay.validation_report,
            "quality": replay.quality_report,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    first = _kpi(replay)
    second = _kpi(replay)
    assert first == second
    assert hashlib.sha256(
        first.canonical_bytes
    ).hexdigest() == first.fingerprint.removeprefix("sha256:")
    after = json.dumps(
        {
            "snapshot": replay.snapshot_document,
            "problem": replay.problem,
            "solution": replay.solution,
            "report": replay.solver_report,
            "validation": replay.validation_report,
            "quality": replay.quality_report,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    assert after == before
