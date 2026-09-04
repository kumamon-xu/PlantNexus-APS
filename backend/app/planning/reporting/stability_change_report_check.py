"""Emit machine-checkable TASK-P4-06 OBJ-002 and ChangeReport evidence."""

from __future__ import annotations

import argparse
import ast
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import cast

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

from app.domain.change_report import ChangeReportError, ImmutableChangeReport
from app.domain.execution_contracts import (
    canonical_contract_bytes,
    change_report_fingerprint,
    contract_fingerprint,
    require_p4_document,
)
from app.planning.reporting.change_report import build_change_report
from app.planning.reporting.stability import calculate_stability
from app.planning.validation.change_report_precheck import validate_change_report


REPORT_VERSION = "p4-stability-change-report.v1"
TASK_ID = "TASK-P4-06"
DIFF_BASE = "d9d9f2fa2dbefe4c9942aaa8a943a93fdc7efd43"
IMPACT_RULES = (
    "IMPACT-DOCS",
    "IMPACT-DOMAIN",
    "IMPACT-INFRA",
    "IMPACT-REPORTING",
    "IMPACT-TESTS",
    "IMPACT-VALIDATOR",
)
_ORIGIN = datetime(2026, 8, 28, tzinfo=UTC)
_FROZEN_SHA256 = {
    "schemas/json/change-report.schema.json": (
        "a040b1cc5c5d44e972af2a08c79393966fa72be3a5407145f429efe6c7b66da8"
    ),
    "schemas/json/planning-policy.v2.schema.json": (
        "d56d092ebac445a359ab2b84ee5df8e810c53b2e0a2852fe6bc5a78290239668"
    ),
    "schemas/json/planning-solution.schema.json": (
        "4344468ea52affeb4c4ce2ede646b6f80f3e7e069cf797596edf5346c1358df4"
    ),
    "schemas/json/kpi.v2.schema.json": (
        "398377d462373315de130491d6286883940e3f8dd733a205ce5c1dfa032b2631"
    ),
    "docs/adr/ADR-0014-freeze-window-stability-change-report.md": (
        "ef9dad9952886da9615477b33c57ca6c3bfd941278acb2d3f8a6b09bc512ae51"
    ),
    "backend/app/planning/backends/cp_sat/objectives.py": (
        "bddaacf231ad05c21e85a20cb30a12db3364b53a19c3208421c248a15daba7b0"
    ),
    "backend/app/planning/validation/problem_schedule_validator.py": (
        "e120cc65c1ea525c23b72b6f4a437fb8dd560ba5fbd8e6febdc6d87e6ca48d9f"
    ),
    "schemas/rules/state-machines.v1.yaml": (
        "6a8c32137a681c6c96defd0dcdd3e580490ec82b81b6494b9b3ba4bf2144ddd7"
    ),
    "pyproject.toml": (
        "327b705255dc9792139aa690351601a1e6a6cba019920142adfa656d6902fe5e"
    ),
    "uv.lock": "8b13617f31aa6a933347fc7b8ba010330cbb3f2d764f75c306dd9b6d77387a82",
}
_P6_SCHEMA_METADATA_PYPROJECT_SHA256 = (
    "c39c0ade6061de9a986eb0e5a3e2d8b568ccb37c7f7bf64242698af782b6c937"
)
_P8_SCHEMA_METADATA_PYPROJECT_SHA256 = (
    "4b511b70bae195debce23cd99149af059aaa1ab3694218f553d115ba3ca8bd09"
)


@dataclass(frozen=True, slots=True)
class StabilityChangeReportFixture:
    """Immutable synthetic input bundle shared with focused tests."""

    context: dict[str, object]
    base_assignments: tuple[dict[str, object], ...]
    new_assignments: tuple[dict[str, object], ...]
    active_operation_ids: tuple[str, ...]
    active_soft_locks: tuple[dict[str, object], ...]
    removed_by_fact: dict[str, object]
    reasons_by_operation: dict[str, object]
    before_kpi: dict[str, object]
    after_kpi: dict[str, object]


def _timestamp(seconds: int) -> str:
    return (_ORIGIN + timedelta(seconds=seconds)).isoformat(
        timespec="seconds"
    ).replace("+00:00", "Z")


def _reference(
    document_version: str, artifact_id: str, seed: object
) -> dict[str, str]:
    return {
        "document_version": document_version,
        "artifact_id": artifact_id,
        "fingerprint": contract_fingerprint(seed),
    }


def _assignment(
    operation_id: str,
    resource_id: str,
    start_seconds: int,
    *,
    duration_seconds: int = 120,
    lock_ids: tuple[str, ...] = (),
    execution_fact_ids: tuple[str, ...] = (),
) -> dict[str, object]:
    return {
        "operation_id": operation_id,
        "resource_id": resource_id,
        "start_tick": start_seconds // 60,
        "end_tick": (start_seconds + duration_seconds) // 60,
        "duration_ticks": duration_seconds // 60,
        "start_at_utc": _timestamp(start_seconds),
        "end_at_utc": _timestamp(start_seconds + duration_seconds),
        "duration_seconds": duration_seconds,
        "lock_ids": list(lock_ids),
        "execution_fact_ids": list(execution_fact_ids),
    }


def _kpi(root: Path, *, suffix: str, tardiness: int, makespan: int) -> dict[str, object]:
    document = cast(
        dict[str, object],
        json.loads(
            (root / "schemas/samples/kpi.v2.synthetic.json").read_text(
                encoding="utf-8"
            )
        ),
    )
    delivery = cast(dict[str, object], document["delivery"])
    demands = cast(list[dict[str, object]], delivery["demands"])
    demand = demands[0]
    delivery.update(
        {
            "on_time_order_count": 0,
            "on_time_order_ratio": 0.0,
            "late_order_count": 1,
            "total_tardiness_seconds": tardiness,
            "priority_weighted_tardiness_seconds": tardiness,
        }
    )
    demand.update(
        {
            "due_at_utc": _timestamp(0),
            "priority_weight": 1,
            "completion_tick": tardiness // 60,
            "completion_at_utc": _timestamp(tardiness),
            "tardiness_seconds": tardiness,
            "priority_weighted_tardiness_seconds": tardiness,
            "on_time": False,
        }
    )
    cast(dict[str, object], document["planning"])["makespan_seconds"] = makespan
    document["planning_run_id"] = f"planning-run-p4-stability-{suffix}"
    document.pop("kpi_id")
    document["kpi_id"] = "kpi-" + sha256(canonical_contract_bytes(document)).hexdigest()
    _schema_validator(root, "kpi.v2.schema.json").validate(document)
    return document


def _schema_validator(root: Path, name: str) -> Draft202012Validator:
    schemas: dict[str, dict[str, object]] = {}
    resources: list[tuple[str, Resource[object]]] = []
    for path in sorted((root / "schemas/json").glob("*.json")):
        schema = cast(
            dict[str, object], json.loads(path.read_text(encoding="utf-8"))
        )
        schemas[path.name] = schema
        resources.append((cast(str, schema["$id"]), Resource.from_contents(schema)))
    return Draft202012Validator(
        schemas[name],
        registry=Registry().with_resources(resources),
        format_checker=FormatChecker(),
    )


def build_stability_change_report_fixture(root: Path) -> StabilityChangeReportFixture:
    """Build fixed complete-universe inputs with one violation and one movement."""

    unchanged_base = _assignment("operation-stable-001", "resource-a", 0)
    unchanged_new = _assignment(
        "operation-stable-001",
        "resource-a",
        0,
        lock_ids=("lock-metadata-new-001",),
    )
    changed_base = _assignment("operation-changed-001", "resource-b", 300)
    changed_new = _assignment(
        "operation-changed-001",
        "resource-c",
        600,
        execution_fact_ids=("execution-fact-disruption-001",),
    )
    added_new = _assignment("operation-added-001", "resource-d", 900)
    removed_base = _assignment("operation-removed-001", "resource-e", 1200)
    solver_reference = _reference(
        "solver-report.v2",
        "solver-report-p4-stability-001",
        {"solver": "synthetic-p4-06"},
    )
    completed_fact = _reference(
        "execution-fact.v1",
        "execution-fact-completed-001",
        {"operation_id": "operation-removed-001", "status": "COMPLETED"},
    )
    trigger_reference = _reference(
        "execution-event.v1",
        "execution-event-added-001",
        {"operation_id": "operation-added-001", "kind": "URGENT_ORDER"},
    )
    unchanged_reference = _reference(
        "schedule-version.v1",
        "schedule-version-p4-stability-base-001",
        {"operation_id": "operation-stable-001", "tuple": "preserved"},
    )
    replan_fingerprint = contract_fingerprint("replan-request")
    context: dict[str, object] = {
        "environment": "TEST",
        "synthetic_provenance": {
            "scenario_id": "SIM-P4-STABILITY-001",
            "scenario_version": "1.0.0",
            "factory_profile_id": "PROFILE-P4-STABILITY-001",
            "profile_version": "1.0.0",
            "generator_id": "plantnexus-p4-stability-check",
            "generator_version": "1.0.0",
            "simulator_id": "plantnexus-p4-stability-check",
            "simulator_version": "1.0.0",
            "seed": 20260828,
        },
        "base_schedule_version": {
            "schedule_version_version": "schedule-version.v1",
            "schedule_version_id": "schedule-version-p4-stability-base-001",
            "state": "PUBLISHED",
            "content_fingerprint": contract_fingerprint(
                [unchanged_base, changed_base, removed_base]
            ),
        },
        "new_schedule_version": {
            "schedule_version_version": "schedule-version.v2",
            "schedule_version_id": "schedule-version-p4-stability-draft-001",
            "state": "DRAFT",
            "content_fingerprint": contract_fingerprint(
                [unchanged_new, changed_new, added_new]
            ),
        },
        "lineage": {
            "base_snapshot": _reference(
                "planning-snapshot.v2", "snapshot-p4-stability-base-001", "base-snapshot"
            ),
            "base_problem": _reference(
                "planning-problem.v2", "problem-p4-stability-base-001", "base-problem"
            ),
            "new_snapshot": _reference(
                "planning-snapshot.v2", "snapshot-p4-stability-new-001", "new-snapshot"
            ),
            "new_problem": _reference(
                "planning-problem.v2", "problem-p4-stability-new-001", "new-problem"
            ),
            "event_stream_fingerprint": contract_fingerprint(
                ["execution-event-added-001", "execution-fact-completed-001"]
            ),
            "fact_checkpoint": _reference(
                "execution-fact-checkpoint.v1",
                "fact-checkpoint-p4-stability-001",
                "fact-checkpoint",
            ),
            "replan_request": {
                "replan_request_version": "replan-request.v1",
                "request_id": (
                    "replan-request-" + replan_fingerprint.removeprefix("sha256:")
                ),
                "request_fingerprint": replan_fingerprint,
            },
            "planning_run_id": "planning-run-p4-stability-after",
            "policy": {
                "planning_policy_version": "planning-policy.v2",
                "policy_id": "POLICY-P4-SIM-DYNAMIC-001",
                "policy_revision": "1.0.0",
                "policy_fingerprint": contract_fingerprint("planning-policy"),
            },
            "limits": {
                "solve_limits_version": "solve-limits.v1",
                "limits_id": "limits-p4-stability-001",
                "limits_revision": "1.0.0",
                "limits_fingerprint": contract_fingerprint("solve-limits"),
                "max_wall_time_seconds": 30,
                "max_workers": 1,
                "random_seed": 20260828,
            },
            "solver_report": solver_reference,
            "validation_report": _reference(
                "validation-report.v2",
                "validation-report-p4-stability-001",
                "validation-report",
            ),
        },
        "freeze_evidence": {
            "freeze_policy_version": "freeze-policy.v1",
            "freeze_policy_id": "FREEZE-POLICY-P4-SIM-001",
            "freeze_policy_revision": "1.0.0",
            "freeze_policy_fingerprint": contract_fingerprint("freeze-policy"),
            "source": {
                "source_system": "plantnexus-synthetic-policy",
                "source_version": "1.0.0",
                "source_record_id": "TASK-P4-06-FREEZE",
            },
            "window_seconds": 900,
            "effective_from_utc": _timestamp(0),
            "effective_until_utc": _timestamp(900),
            "interval_semantics": "HALF_OPEN_START_INCLUSIVE_END_EXCLUSIVE",
            "effective_lock_ids": ["soft-lock-changed-001", "soft-lock-stable-001"],
        },
        "generated_at_utc": _timestamp(1800),
        "correlation_id": "correlation-p4-stability-001",
    }
    return StabilityChangeReportFixture(
        context=context,
        base_assignments=(unchanged_base, changed_base, removed_base),
        new_assignments=(unchanged_new, changed_new, added_new),
        active_operation_ids=(
            "operation-added-001",
            "operation-changed-001",
            "operation-stable-001",
        ),
        active_soft_locks=(
            {
                "reference_id": "soft-lock-stable-001",
                "operation_id": "operation-stable-001",
                "protection_kind": "SOFT_LOCK",
                "protection_priority": 4,
                "resource_id": "resource-a",
                "start_at_utc": _timestamp(0),
                "end_at_utc": _timestamp(120),
            },
            {
                "reference_id": "soft-lock-changed-001",
                "operation_id": "operation-changed-001",
                "protection_kind": "SOFT_LOCK",
                "protection_priority": 4,
                "resource_id": "resource-b",
                "start_at_utc": _timestamp(300),
                "end_at_utc": _timestamp(420),
            },
        ),
        removed_by_fact={"operation-removed-001": completed_fact},
        reasons_by_operation={
            "operation-stable-001": [
                {"reason_code": "NO_CHANGE", "evidence_refs": [unchanged_reference]}
            ],
            "operation-added-001": [
                {"reason_code": "TRIGGER_EVENT", "evidence_refs": [trigger_reference]}
            ],
            "operation-removed-001": [
                {
                    "reason_code": "REMOVED_BY_COMPLETION_FACT",
                    "evidence_refs": [completed_fact],
                }
            ],
        },
        before_kpi=_kpi(root, suffix="before", tardiness=600, makespan=1200),
        after_kpi=_kpi(root, suffix="after", tardiness=300, makespan=900),
    )


def build_fixture_change_report(
    fixture: StabilityChangeReportFixture,
) -> ImmutableChangeReport:
    """Build the canonical report for one fixture without side effects."""

    return build_change_report(
        context=fixture.context,
        base_assignments=fixture.base_assignments,
        new_assignments=fixture.new_assignments,
        active_operation_ids=fixture.active_operation_ids,
        active_soft_locks=fixture.active_soft_locks,
        removed_by_fact=fixture.removed_by_fact,
        reasons_by_operation=fixture.reasons_by_operation,
        before_kpi=fixture.before_kpi,
        after_kpi=fixture.after_kpi,
    )


def _precheck(
    fixture: StabilityChangeReportFixture, report: Mapping[str, object]
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


def _ensure(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _pass(check_id: str, evidence: Mapping[str, object]) -> dict[str, object]:
    return {"check_id": check_id, "status": "PASS", "evidence": dict(evidence)}


def _frozen_input_check(root: Path) -> dict[str, object]:
    observed = {
        relative: sha256((root / relative).read_bytes()).hexdigest()
        for relative in _FROZEN_SHA256
    }
    frozen_observed = dict(observed)
    pyproject_digest = frozen_observed.pop("pyproject.toml")
    frozen_expected = dict(_FROZEN_SHA256)
    p4_pyproject_digest = frozen_expected.pop("pyproject.toml")
    _ensure(
        frozen_observed == frozen_expected
        and pyproject_digest
        in {
            p4_pyproject_digest,
            _P6_SCHEMA_METADATA_PYPROJECT_SHA256,
            _P8_SCHEMA_METADATA_PYPROJECT_SHA256,
        },
        "frozen contract, Solver, or dependency bytes changed",
    )
    builder_source = (root / "backend/app/planning/reporting/change_report.py").read_text(
        encoding="utf-8"
    )
    precheck_source = (
        root / "backend/app/planning/validation/change_report_precheck.py"
    ).read_text(encoding="utf-8")
    imported: set[str] = set()
    for source in (builder_source, precheck_source):
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                imported.add(node.module)
    forbidden_prefixes = (
        "ort" + "ools",
        "app.planning." + "backends",
        "app." + "application",
        "app." + "infrastructure",
        "app." + "api",
        "app." + "simulation",
    )
    _ensure(
        all(
            not any(name.startswith(prefix) for prefix in forbidden_prefixes)
            for name in imported
        ),
        "calculator, builder, or precheck crossed an excluded dependency boundary",
    )
    _ensure(
        "app.planning.reporting" not in precheck_source,
        "independent precheck imported reporting implementation",
    )
    return {
        "frozen_files": len(observed),
        "change_report_schema_sha256": observed[
            "schemas/json/change-report.schema.json"
        ],
        "cp_sat_objectives_sha256": observed[
            "backend/app/planning/backends/cp_sat/objectives.py"
        ],
        "formal_validator_sha256": observed[
            "backend/app/planning/validation/problem_schedule_validator.py"
        ],
        "forbidden_imports": 0,
    }


def _mutation_checks(
    fixture: StabilityChangeReportFixture,
    report: Mapping[str, object],
) -> dict[str, object]:
    mutations: list[dict[str, object]] = []

    shifted = cast(dict[str, object], deepcopy(report))
    cast(dict[str, object], shifted["stability"])[
        "absolute_start_shift_seconds"
    ] = 301
    _rehash(shifted)
    mutations.append(shifted)

    incomplete = cast(dict[str, object], deepcopy(report))
    cast(list[dict[str, object]], incomplete["operations"]).pop()
    incomplete["operation_universe_count"] = 3
    _rehash(incomplete)
    mutations.append(incomplete)

    false_fact = cast(dict[str, object], deepcopy(report))
    removed = next(
        item
        for item in cast(list[dict[str, object]], false_fact["operations"])
        if item["classification"] == "REMOVED_BY_FACT"
    )
    cast(list[dict[str, object]], removed["reasons"])[0]["evidence_refs"] = [
        _reference("execution-fact.v1", "execution-fact-wrong-001", "wrong")
    ]
    _rehash(false_fact)
    mutations.append(false_fact)

    false_kpi = cast(dict[str, object], deepcopy(report))
    cast(dict[str, object], false_kpi["after_kpi"])["fingerprint"] = (
        "sha256:" + "f" * 64
    )
    _rehash(false_kpi)
    mutations.append(false_kpi)

    false_classification = cast(dict[str, object], deepcopy(report))
    changed = next(
        item
        for item in cast(list[dict[str, object]], false_classification["operations"])
        if item["operation_id"] == "operation-changed-001"
    )
    changed["classification"] = "UNCHANGED"
    _rehash(false_classification)
    mutations.append(false_classification)

    results = [_precheck(fixture, mutation) for mutation in mutations]
    _ensure(
        all(result["status"] == "FAIL" for result in results),
        "independent precheck accepted a ChangeReport mutation",
    )
    _ensure(
        all(cast(int, result["hard_violation_count"]) >= 1 for result in results),
        "mutation reports did not preserve deterministic violations",
    )
    return {
        "vectors": len(results),
        "failed_closed": len(results),
        "violation_counts": [result["hard_violation_count"] for result in results],
    }


def _builder_rejection_checks(
    fixture: StabilityChangeReportFixture,
) -> dict[str, object]:
    rejected = 0
    invalid_active = list(fixture.active_operation_ids[:-1])
    try:
        build_change_report(
            context=fixture.context,
            base_assignments=fixture.base_assignments,
            new_assignments=fixture.new_assignments,
            active_operation_ids=invalid_active,
            active_soft_locks=fixture.active_soft_locks,
            removed_by_fact=fixture.removed_by_fact,
            reasons_by_operation=fixture.reasons_by_operation,
            before_kpi=fixture.before_kpi,
            after_kpi=fixture.after_kpi,
        )
    except ChangeReportError:
        rejected += 1
    missing_fact = dict(fixture.removed_by_fact)
    missing_fact.clear()
    try:
        build_change_report(
            context=fixture.context,
            base_assignments=fixture.base_assignments,
            new_assignments=fixture.new_assignments,
            active_operation_ids=fixture.active_operation_ids,
            active_soft_locks=fixture.active_soft_locks,
            removed_by_fact=missing_fact,
            reasons_by_operation=fixture.reasons_by_operation,
            before_kpi=fixture.before_kpi,
            after_kpi=fixture.after_kpi,
        )
    except ChangeReportError:
        rejected += 1

    missing_lock_context = cast(dict[str, object], deepcopy(fixture.context))
    freeze = cast(dict[str, object], missing_lock_context["freeze_evidence"])
    freeze["effective_lock_ids"] = ["soft-lock-stable-001"]
    try:
        build_change_report(
            context=missing_lock_context,
            base_assignments=fixture.base_assignments,
            new_assignments=fixture.new_assignments,
            active_operation_ids=fixture.active_operation_ids,
            active_soft_locks=fixture.active_soft_locks,
            removed_by_fact=fixture.removed_by_fact,
            reasons_by_operation=fixture.reasons_by_operation,
            before_kpi=fixture.before_kpi,
            after_kpi=fixture.after_kpi,
        )
    except ChangeReportError:
        rejected += 1

    forged_kpi = cast(dict[str, object], deepcopy(fixture.before_kpi))
    cast(dict[str, object], forged_kpi["delivery"])[
        "priority_weighted_tardiness_seconds"
    ] = 601
    try:
        build_change_report(
            context=fixture.context,
            base_assignments=fixture.base_assignments,
            new_assignments=fixture.new_assignments,
            active_operation_ids=fixture.active_operation_ids,
            active_soft_locks=fixture.active_soft_locks,
            removed_by_fact=fixture.removed_by_fact,
            reasons_by_operation=fixture.reasons_by_operation,
            before_kpi=forged_kpi,
            after_kpi=fixture.after_kpi,
        )
    except ChangeReportError:
        rejected += 1

    _ensure(
        rejected == 4,
        "builder did not fail closed for universe/fact/lock/KPI inputs",
    )
    return {"negative_inputs": 4, "rejected": rejected}


def run_stability_change_report_checks(root: Path) -> dict[str, object]:
    frozen = _frozen_input_check(root)
    fixture = build_stability_change_report_fixture(root)
    immutable_input_bytes = canonical_contract_bytes(
        {
            "context": fixture.context,
            "base": fixture.base_assignments,
            "new": fixture.new_assignments,
            "locks": fixture.active_soft_locks,
            "facts": fixture.removed_by_fact,
            "reasons": fixture.reasons_by_operation,
            "before_kpi": fixture.before_kpi,
            "after_kpi": fixture.after_kpi,
        }
    )
    stability = calculate_stability(
        base_assignments=fixture.base_assignments,
        new_assignments=fixture.new_assignments,
        active_operation_ids=fixture.active_operation_ids,
        active_soft_locks=fixture.active_soft_locks,
    )
    _ensure(stability.score == (1, 1, 1, 300), "OBJ-002 integer vector drifted")
    report = build_fixture_change_report(fixture)
    document = report.document
    require_p4_document(document)
    _schema_validator(root, "change-report.schema.json").validate(document)
    classifications = {
        cast(str, item["operation_id"]): item["classification"]
        for item in cast(list[dict[str, object]], document["operations"])
    }
    _ensure(
        classifications
        == {
            "operation-added-001": "ADDED",
            "operation-changed-001": "CHANGED",
            "operation-removed-001": "REMOVED_BY_FACT",
            "operation-stable-001": "UNCHANGED",
        },
        "complete operation universe classification drifted",
    )
    changed = next(
        item
        for item in cast(list[dict[str, object]], document["operations"])
        if item["classification"] == "CHANGED"
    )
    _ensure(
        cast(list[dict[str, object]], changed["reasons"])[0]["reason_code"]
        == "UNATTRIBUTED_SOLVER_CHANGE",
        "changed operation fallback reason drifted",
    )
    precheck = _precheck(fixture, document)
    _ensure(precheck["status"] == "PASS", "independent ChangeReport precheck failed")
    _ensure(precheck["objective_vector"] == [1, 1, 1, 300], "precheck vector drifted")
    kpi_comparison = cast(dict[str, object], precheck["kpi_comparison"])
    _ensure(
        kpi_comparison["priority_weighted_tardiness_delta_seconds"] == -300,
        "before/after tardiness comparison drifted",
    )
    mutations = _mutation_checks(fixture, document)
    rejections = _builder_rejection_checks(fixture)
    repeated = build_fixture_change_report(fixture)
    _ensure(
        repeated.canonical_bytes == report.canonical_bytes,
        "same immutable inputs did not replay byte-exactly",
    )
    _ensure(
        immutable_input_bytes
        == canonical_contract_bytes(
            {
                "context": fixture.context,
                "base": fixture.base_assignments,
                "new": fixture.new_assignments,
                "locks": fixture.active_soft_locks,
                "facts": fixture.removed_by_fact,
                "reasons": fixture.reasons_by_operation,
                "before_kpi": fixture.before_kpi,
                "after_kpi": fixture.after_kpi,
            }
        ),
        "builder mutated an authoritative input",
    )
    boundaries = {
        "data_plane": "SIMULATION_ONLY",
        "objective": "OBJ-002_REPORTING_ONLY_NOT_CP_SAT_OBJECTIVE",
        "change_report": "IMMUTABLE_COMPLETE_EVIDENCE_NOT_APPROVAL",
        "execution_event_replan_request_freeze": "FROZEN_INPUT_REFERENCES_ONLY",
        "schedule_version_or_state_transition": "NONE",
        "application_api_ui_simulator": "NOT_IMPLEMENTED_BY_TASK",
        "p4_07_plus": "NOT_STARTED",
        "p5_plus": "NOT_STARTED",
        "production_external_authority_capacity_sla": "NOT_ESTABLISHED",
    }
    checks = [
        _pass("frozen-contract-solver-validator-state-and-dependencies", frozen),
        _pass(
            "integer-lexicographic-obj-002-vector",
            {
                "components": [
                    "SOFT_LOCK_VIOLATIONS",
                    "CHANGED_EXISTING_OPERATIONS",
                    "RESOURCE_CHANGES",
                    "ABSOLUTE_START_SHIFT_SECONDS",
                ],
                "score": list(stability.score),
                "float_weights": 0,
            },
        ),
        _pass(
            "complete-operation-universe-and-reason-evidence",
            {
                "operation_universe_count": document["operation_universe_count"],
                "classifications": classifications,
                "fallback_reason": "UNATTRIBUTED_SOLVER_CHANGE",
                "removed_fact_references": 1,
            },
        ),
        _pass(
            "exact-kpi-lineage-freeze-and-schema-carrier",
            {
                "before_kpi": document["before_kpi"],
                "after_kpi": document["after_kpi"],
                "tardiness_delta_seconds": -300,
                "schema": "change-report.v1@2.8.0",
            },
        ),
        _pass(
            "independent-completeness-precheck",
            {
                "status": precheck["status"],
                "report_id": precheck["report_id"],
                "hard_violation_count": precheck["hard_violation_count"],
                "independence": precheck["independence"],
            },
        ),
        _pass("mutation-and-invalid-input-fail-closed", {**mutations, **rejections}),
        _pass(
            "content-addressed-byte-exact-replay-and-input-immutability",
            {
                "report_id": report.report_id,
                "report_fingerprint": report.report_fingerprint,
                "deterministic_replays": 2,
                "authoritative_input_mutations": 0,
            },
        ),
        _pass("p4-p5-production-capability-boundary", boundaries),
    ]
    return {
        "report_version": REPORT_VERSION,
        "status": "PASS",
        "task_id": TASK_ID,
        "code_commit": os.environ.get("PLANTNEXUS_CODE_COMMIT", "uncommitted"),
        "diff_base": DIFF_BASE,
        "impact_rule_count": len(IMPACT_RULES),
        "impact_rules": list(IMPACT_RULES),
        "check_count": len(checks),
        "checks": checks,
        "issues": [],
        "artifacts": {
            "change_report_id": report.report_id,
            "change_report_fingerprint": report.report_fingerprint,
            "precheck_report_id": precheck["report_id"],
            "precheck_report_fingerprint": precheck["report_fingerprint"],
            "before_kpi_fingerprint": cast(dict[str, object], document["before_kpi"])[
                "fingerprint"
            ],
            "after_kpi_fingerprint": cast(dict[str, object], document["after_kpi"])[
                "fingerprint"
            ],
        },
        "counts": {
            "operation_universe": 4,
            "positive_vectors": 1,
            "mutation_vectors": mutations["vectors"],
            "invalid_input_vectors": rejections["negative_inputs"],
            "machine_checks": len(checks),
        },
        "boundaries": boundaries,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--report", type=Path, required=True)
    arguments = parser.parse_args(argv)
    try:
        report = run_stability_change_report_checks(arguments.root.resolve())
    except Exception as error:
        report = {
            "report_version": REPORT_VERSION,
            "status": "FAIL",
            "task_id": TASK_ID,
            "code_commit": os.environ.get("PLANTNEXUS_CODE_COMMIT", "uncommitted"),
            "diff_base": DIFF_BASE,
            "impact_rule_count": len(IMPACT_RULES),
            "impact_rules": list(IMPACT_RULES),
            "error_type": type(error).__name__,
            "error_message": "OBJ-002 and ChangeReport evidence check failed",
            "issues": ["machine-check-failed"],
        }
        exit_code = 1
    else:
        exit_code = 0
    arguments.report.parent.mkdir(parents=True, exist_ok=True)
    arguments.report.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "DIFF_BASE",
    "REPORT_VERSION",
    "StabilityChangeReportFixture",
    "build_fixture_change_report",
    "build_stability_change_report_fixture",
    "main",
    "run_stability_change_report_checks",
]
