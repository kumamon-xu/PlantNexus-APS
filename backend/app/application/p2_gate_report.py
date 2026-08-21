"""Aggregate the complete P2 Simulation vertical slice into one Gate report.

This module is intentionally an orchestrator.  It calls the published P2
correctness, benchmark, planning-contract, and internal-export boundaries; it
does not repair or reimplement any Solver, Validator, contract, fixture, or
benchmark behavior.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from hashlib import sha256
import json
import os
from pathlib import Path
from time import perf_counter
from typing import Any, Never, cast

from app.domain.capabilities import (
    CapabilityContractError,
    CapabilityName,
    require_v1_capability_contract,
)
from app.exporters.contract_check import run_output_contract_checks
from app.planning.contracts import (
    PlanningContractError,
    SolverStatus,
    outcome_document_for_status,
    outcome_for_solver_status,
)
from app.planning.policy import (
    simulation_solve_limits,
    validate_solve_limits,
)
from app.planning.problem import (
    ImmutablePlanningProblemV2,
    PlanningProblemError,
    verify_problem_v2,
)
from app.simulation.benchmarks import run_benchmark, validate_benchmark_report
from app.simulation.scenarios.p2_correctness import run_correctness_checks


REPORT_VERSION = "p2-vertical-slice-report.v1"
SEMANTIC_PROJECTION_VERSION = "p2-gate-semantic-projection.v1"
TASK_ID = "TASK-P2-13"

type JsonObject = dict[str, Any]

_EXPECTED_SCENARIOS = (
    "P2-GOLDEN-JSSP",
    "P2-GOLDEN-FJSP",
    "P2-CROSS-WORKSHOP",
    "P2-CALENDAR",
    "P2-MATERIAL-DELAY",
    "P2-RUNNING",
    "P2-HARD-LOCK",
)
_EXPECTED_CONSTRAINT_IDS = tuple(f"C-{index:03d}" for index in range(1, 12))
_EXPECTED_BENCHMARK_SIZES = ("XS", "S", "M")
_EXPECTED_REJECTION_IDS = (
    "UNSUPPORTED_CAPABILITY",
    "INVALID_PLANNING_PROBLEM",
    "INVALID_SOLVE_LIMITS",
    "NO_SOLUTION_WITHIN_LIMIT",
)
_EXPECTED_CHECKS = (
    "public-snapshot-problem-policy-solver-validator-export-chain",
    "two-or-more-complete-gate-replays",
    "seven-versioned-correctness-scenarios",
    "c001-c011-positive-and-negative-validator-evidence",
    "xs-s-m-global-and-reference-benchmark-evidence",
    "independent-validator-pass-on-every-candidate",
    "objective-status-model-timing-and-memory-evidence",
    "kpi-solver-report-and-internal-export-evidence",
    "four-fail-closed-unsupported-invalid-and-limit-cases",
    "stable-business-semantic-hashes-across-replays",
    "p2-evidence-only-non-exit-non-production-boundary",
)
_BOUNDARIES: JsonObject = {
    "current_phase": "P2",
    "data_plane": "SIMULATION_ONLY",
    "gate_kind": "P2_VERTICAL_SLICE_EVIDENCE_NOT_EXIT_AUDIT",
    "exit_gate_decision": "NOT_PERFORMED",
    "p2_14": "NOT_STARTED",
    "p3": "NOT_STARTED",
    "production_readiness": "NOT_CLAIMED",
    "production_capacity_sla": "NOT_ESTABLISHED_OPEN_011_012",
    "remediation": "NONE_MIXED_INTO_GATE",
    "schema_migration_dependency_adr_changes": "NONE",
}


class P2GateContractError(ValueError):
    """A subordinate report or aggregate Gate report violates the contract."""

    def __init__(self, field: str, message: str) -> None:
        self.field = field
        self.message = message
        super().__init__(f"P2_GATE_CONTRACT at {field}: {message}")


class P2GateExecutionError(RuntimeError):
    """One public boundary failed while a complete Gate replay was running."""

    def __init__(self, stage: str, error: Exception) -> None:
        self.stage = stage
        self.error_type = type(error).__name__
        self.error_message = str(error)
        super().__init__(
            f"P2_GATE_STAGE_FAILED at {stage}: {self.error_type}: "
            f"{self.error_message}"
        )


def _fail(field: str, message: str) -> Never:
    raise P2GateContractError(field, message)


def _object(value: object, field: str) -> JsonObject:
    if not isinstance(value, dict):
        _fail(field, "expected a JSON object")
    return cast(JsonObject, value)


def _items(value: object, field: str) -> list[Any]:
    if not isinstance(value, list):
        _fail(field, "expected a JSON array")
    return cast(list[Any], value)


def _exact_keys(document: Mapping[str, object], expected: set[str], field: str) -> None:
    observed = set(document)
    if observed != expected:
        _fail(
            field,
            f"missing={sorted(expected - observed)} extra={sorted(observed - expected)}",
        )


def _sha256(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{sha256(payload).hexdigest()}"


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 71
        and value.startswith("sha256:")
        and all(character in "0123456789abcdef" for character in value[7:])
    )


def _code_commit() -> str:
    value = os.environ.get("PLANTNEXUS_CODE_COMMIT", "uncommitted")
    if value == "uncommitted" or (
        len(value) == 40
        and all(character in "0123456789abcdef" for character in value)
    ):
        return value
    return "uncommitted"


def _generated_at() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _checks_by_name(report: Mapping[str, object], field: str) -> dict[str, JsonObject]:
    result: dict[str, JsonObject] = {}
    for index, raw_check in enumerate(_items(report.get("checks"), f"{field}.checks")):
        check = _object(raw_check, f"{field}.checks[{index}]")
        name = check.get("name")
        if not isinstance(name, str) or not name or name in result:
            _fail(f"{field}.checks[{index}].name", "check name must be unique text")
        if check.get("status") != "PASS":
            _fail(f"{field}.checks[{index}].status", "subordinate check is not PASS")
        result[name] = check
    if report.get("check_count") != len(result):
        _fail(f"{field}.check_count", "does not match unique checks")
    return result


def _require_subreport(
    report: JsonObject,
    *,
    field: str,
    version_field: str,
    version: str,
    task_id: str,
    code_commit: str,
) -> dict[str, JsonObject]:
    if report.get(version_field) != version:
        _fail(f"{field}.{version_field}", f"expected {version}")
    if report.get("status") != "PASS":
        _fail(f"{field}.status", "subordinate report is not PASS")
    if report.get("task_id") != task_id:
        _fail(f"{field}.task_id", f"expected {task_id}")
    if report.get("code_commit") != code_commit:
        _fail(
            f"{field}.code_commit",
            "subordinate report is not bound to the Gate code commit",
        )
    return _checks_by_name(report, field)


def _validate_correctness_report(report: JsonObject, code_commit: str) -> None:
    checks = _require_subreport(
        report,
        field="correctness",
        version_field="report_version",
        version="p2-correctness-report.v1",
        task_id="TASK-P2-09",
        code_commit=code_commit,
    )
    expected_checks = {
        "frozen-schema-problem-strategy-validator-policy-generator-and-lock",
        "p0-p1-immutable-asset-manifest",
        "seven-versioned-profile-scenario-blueprint-manifest-assets",
        "formal-ingress-snapshot-problem-replay",
        "golden-jssp-fjsp-manual-optimum-and-validator",
        "five-scenario-correctness-matrix",
        "solver-generated-property-and-reordering-replay",
        "formula-free-exact-c001-c011-validator-mutations",
    }
    if set(checks) != expected_checks:
        _fail("correctness.checks", "correctness check inventory changed")
    counts = _object(report.get("counts"), "correctness.counts")
    expected_counts = {
        "scenario_cases": 7,
        "golden_cases": 2,
        "matrix_cases": 5,
        "solver_candidates": 7,
        "independent_validator_passes": 7,
        "property_replays": 7,
        "mutation_cases": 11,
        "constraints_positive_covered": 11,
        "constraints_negative_covered": 11,
    }
    if counts != expected_counts:
        _fail("correctness.counts", "expected the complete seven-scenario matrix")

    replay_rows = _items(
        checks["formal-ingress-snapshot-problem-replay"].get("details"),
        "correctness.formal_replays",
    )
    if tuple(row.get("scenario_id") for row in replay_rows) != _EXPECTED_SCENARIOS:
        _fail("correctness.formal_replays", "scenario identity/order changed")
    for index, raw_row in enumerate(replay_rows):
        row = _object(raw_row, f"correctness.formal_replays[{index}]")
        if row.get("solver_status") not in {"OPTIMAL", "FEASIBLE"}:
            _fail(f"correctness.formal_replays[{index}].solver_status", "no candidate")
        if row.get("validator_status") != "PASS" or row.get("hard_violation_count") != 0:
            _fail(f"correctness.formal_replays[{index}]", "Validator did not pass")
        for hash_field in ("import_dataset_hash", "snapshot_hash", "problem_hash"):
            if not _is_sha256(row.get(hash_field)):
                _fail(
                    f"correctness.formal_replays[{index}].{hash_field}",
                    "missing content hash",
                )
        metrics = _object(
            row.get("model_metrics"),
            f"correctness.formal_replays[{index}].model_metrics",
        )
        if any(
            not isinstance(metrics.get(name), int) or metrics[name] <= 0
            for name in ("variables", "constraints")
        ):
            _fail(
                f"correctness.formal_replays[{index}].model_metrics",
                "model cardinality is absent",
            )

    mutation_rows = _items(
        checks["formula-free-exact-c001-c011-validator-mutations"].get(
            "details"
        ),
        "correctness.mutations",
    )
    if tuple(row.get("constraint_id") for row in mutation_rows) != (
        _EXPECTED_CONSTRAINT_IDS
    ):
        _fail("correctness.mutations", "C-001 through C-011 coverage changed")
    if any(
        row.get("status") != "FAIL"
        or row.get("hard_violation_count", 0) < 1
        or row.get("deterministic_replay") is not True
        for row in mutation_rows
    ):
        _fail("correctness.mutations", "negative Validator evidence is incomplete")


def _validate_non_negative_samples(value: object, field: str) -> None:
    metrics = _object(value, field)
    samples = _items(metrics.get("samples"), f"{field}.samples")
    if not samples or any(
        isinstance(sample, bool)
        or not isinstance(sample, (int, float))
        or float(sample) < 0
        for sample in samples
    ):
        _fail(field, "timing/memory samples must be non-negative numbers")


def _validate_benchmark_report(
    report: JsonObject,
    *,
    size: str,
    code_commit: str,
) -> None:
    validate_benchmark_report(report)
    _require_subreport(
        report,
        field=f"benchmarks.{size}",
        version_field="benchmark_report_version",
        version="benchmark-report.v1",
        task_id="TASK-P2-12",
        code_commit=code_commit,
    )
    profile = _object(report.get("profile"), f"benchmarks.{size}.profile")
    if profile.get("size") != size:
        _fail(f"benchmarks.{size}.profile.size", f"expected {size}")
    if report.get("warnings") != []:
        _fail(f"benchmarks.{size}.warnings", "Gate requires a warning-free baseline")
    baseline = _object(report.get("baseline"), f"benchmarks.{size}.baseline")
    if baseline.get("status") != "PASS":
        _fail(f"benchmarks.{size}.baseline", "baseline comparison did not pass")
    problem = _object(report.get("problem"), f"benchmarks.{size}.problem")
    if not _is_sha256(problem.get("problem_hash")) or not _is_sha256(
        problem.get("snapshot_hash")
    ):
        _fail(f"benchmarks.{size}.problem", "Problem/Snapshot hashes are absent")
    complexity = _object(
        problem.get("complexity"), f"benchmarks.{size}.problem.complexity"
    )
    if complexity.get("operation_count", 0) <= 0 or complexity.get(
        "resource_count", 0
    ) <= 0:
        _fail(f"benchmarks.{size}.problem.complexity", "scale is empty")

    pipeline = _object(report.get("pipeline"), f"benchmarks.{size}.pipeline")
    if (
        pipeline.get("kpi_version") != "kpi.v2"
        or pipeline.get("export_package_profile") != "p2-internal-export.v1"
        or pipeline.get("export_file_count") != 9
        or not _is_sha256(pipeline.get("export_manifest_fingerprint"))
    ):
        _fail(f"benchmarks.{size}.pipeline", "KPI/Export evidence is incomplete")

    global_solver = _object(
        report.get("global_solver"), f"benchmarks.{size}.global_solver"
    )
    if global_solver.get("status") not in {"OPTIMAL", "FEASIBLE"}:
        _fail(f"benchmarks.{size}.global_solver.status", "candidate is absent")
    validation = _object(
        global_solver.get("validation"),
        f"benchmarks.{size}.global_solver.validation",
    )
    if (
        validation.get("status") != "PASS"
        or validation.get("fresh_formal") is not True
        or validation.get("pass_count") != profile.get("measured_runs")
    ):
        _fail(
            f"benchmarks.{size}.global_solver.validation",
            "fresh independent Validator evidence is incomplete",
        )
    model_metrics = _object(
        global_solver.get("model_metrics"),
        f"benchmarks.{size}.global_solver.model_metrics",
    )
    if any(
        not isinstance(model_metrics.get(name), int) or model_metrics[name] <= 0
        for name in ("variables", "constraints")
    ):
        _fail(
            f"benchmarks.{size}.global_solver.model_metrics",
            "model cardinality is absent",
        )
    quality = _object(
        global_solver.get("quality"), f"benchmarks.{size}.global_solver.quality"
    )
    for name in ("objective", "best_bound", "relative_gap"):
        if isinstance(quality.get(name), bool) or not isinstance(
            quality.get(name), (int, float)
        ):
            _fail(
                f"benchmarks.{size}.global_solver.quality.{name}",
                "objective evidence is absent",
            )
    timings = _object(
        global_solver.get("timings"), f"benchmarks.{size}.global_solver.timings"
    )
    for name in (
        "model_build_seconds",
        "first_solution_seconds",
        "solve_seconds",
        "validation_seconds",
        "total_seconds",
    ):
        _validate_non_negative_samples(
            timings.get(name), f"benchmarks.{size}.global_solver.timings.{name}"
        )
    _validate_non_negative_samples(
        global_solver.get("memory_peak_mb"),
        f"benchmarks.{size}.global_solver.memory_peak_mb",
    )
    samples = _items(
        global_solver.get("sample_fingerprints"),
        f"benchmarks.{size}.global_solver.sample_fingerprints",
    )
    if len(set(samples)) != 1 or not all(_is_sha256(value) for value in samples):
        _fail(
            f"benchmarks.{size}.global_solver.sample_fingerprints",
            "measured candidate hashes are not deterministic",
        )

    references = _items(
        report.get("reference_schedulers"), f"benchmarks.{size}.references"
    )
    if len(references) != 5:
        _fail(f"benchmarks.{size}.references", "expected five reference schedulers")
    for index, raw_reference in enumerate(references):
        reference = _object(
            raw_reference, f"benchmarks.{size}.references[{index}]"
        )
        reference_validation = _object(
            reference.get("validation"),
            f"benchmarks.{size}.references[{index}].validation",
        )
        if (
            reference.get("status") != "FEASIBLE"
            or reference.get("deterministic_replay") is not True
            or reference_validation.get("status") != "PASS"
            or reference_validation.get("fresh_formal") is not True
        ):
            _fail(
                f"benchmarks.{size}.references[{index}]",
                "reference candidate/Validator evidence is incomplete",
            )


def _validate_output_report(report: JsonObject, code_commit: str) -> None:
    checks = _require_subreport(
        report,
        field="export",
        version_field="report_version",
        version="p2-output-contract-report.v1",
        task_id="TASK-P2-11",
        code_commit=code_commit,
    )
    if report.get("package_profile") != "p2-internal-export.v1":
        _fail("export.package_profile", "unexpected package profile")
    counts = _object(report.get("counts"), "export.counts")
    if counts != {
        "package_files_excluding_manifest": 9,
        "assignments": 4,
        "demands": 2,
        "resources": 2,
        "rejection_cases": 3,
        "deterministic_replays": 2,
    }:
        _fail("export.counts", "output contract coverage changed")
    package = _object(
        checks["deterministic-package-bytes-file-hashes-and-row-counts"].get(
            "details"
        ),
        "export.package",
    )
    if (
        package.get("file_count") != 9
        or not _is_sha256(package.get("manifest_fingerprint"))
        or not str(package.get("package_id", "")).startswith("export-package-")
    ):
        _fail("export.package", "deterministic package evidence is incomplete")
    files = _items(package.get("files"), "export.package.files")
    if len(files) != 9 or any(not _is_sha256(row.get("sha256")) for row in files):
        _fail("export.package.files", "file hashes are incomplete")


def _stable_correctness_projection(report: JsonObject) -> JsonObject:
    projection = cast(JsonObject, json.loads(json.dumps(report)))
    projection.pop("generated_at", None)
    projection.pop("code_commit", None)
    return projection


def _stable_benchmark_projection(report: JsonObject) -> JsonObject:
    pipeline = _object(report["pipeline"], "benchmark.pipeline")
    global_solver = _object(report["global_solver"], "benchmark.global_solver")
    references = _items(report["reference_schedulers"], "benchmark.references")
    baseline = _object(report["baseline"], "benchmark.baseline")
    return {
        "benchmark_report_version": report["benchmark_report_version"],
        "status": report["status"],
        "profile_set_version": report["profile_set_version"],
        "runner_version": report["runner_version"],
        "threshold_policy_version": report["threshold_policy_version"],
        "schema_set_version": report["schema_set_version"],
        "profile": report["profile"],
        "scenario": report["scenario"],
        "generator": report["generator"],
        "assembler": report["assembler"],
        "pipeline": {
            "versions": pipeline["versions"],
            "kpi_version": pipeline["kpi_version"],
            "export_package_profile": pipeline["export_package_profile"],
            "export_file_count": pipeline["export_file_count"],
        },
        "problem": report["problem"],
        "environment": report["environment"],
        "execution": report["execution"],
        "global_solver": {
            key: global_solver[key]
            for key in (
                "status",
                "strategy_id",
                "strategy_version",
                "solver",
                "parameters",
                "model_metrics",
                "quality",
                "validation",
                "sample_fingerprints",
            )
        },
        "reference_schedulers": [
            {
                key: reference[key]
                for key in (
                    "algorithm",
                    "algorithm_id",
                    "status",
                    "non_production",
                    "optimality_claim",
                    "quality",
                    "validation",
                    "sample_fingerprints",
                    "deterministic_replay",
                )
            }
            for reference in references
        ],
        "comparison": report["comparison"],
        "baseline": {
            key: baseline[key]
            for key in (
                "benchmark_baseline_version",
                "path",
                "status",
                "environment_comparable",
                "checks",
            )
        },
        "checks": [
            {"name": check["name"], "status": check["status"]}
            for check in _items(report["checks"], "benchmark.checks")
        ],
        "warnings": report["warnings"],
        "boundaries": report["boundaries"],
    }


def _stable_output_projection(report: JsonObject) -> JsonObject:
    checks = _checks_by_name(report, "export")
    package = _object(
        checks["deterministic-package-bytes-file-hashes-and-row-counts"]["details"],
        "export.package",
    )
    lineage = _object(
        checks["cross-file-run-hash-version-and-entity-count-lineage"]["details"],
        "export.lineage",
    )
    lineage_documents = _object(lineage["lineage"], "export.lineage.documents")
    return {
        "report_version": report["report_version"],
        "status": report["status"],
        "schema_set_version": report["schema_set_version"],
        "package_profile": report["package_profile"],
        "scenario_id": report["scenario_id"],
        "counts": report["counts"],
        "frozen_inputs": checks[
            "frozen-input-contracts-new-schemas-samples-and-lock"
        ]["details"],
        "schema_contract": checks[
            "kpi-v2-and-export-manifest-draft-2020-12-roundtrip"
        ]["details"],
        "package_files": [
            {
                key: row[key]
                for key in ("path", "role", "media_type", "row_count")
            }
            for row in _items(package["files"], "export.package.files")
        ],
        "entity_counts": lineage["entity_counts"],
        "lineage": {
            "import_quality_report": {
                "report_version": lineage_documents["import_quality_report"][
                    "report_version"
                ],
                "status": lineage_documents["import_quality_report"]["status"],
            },
            "kpi_version": lineage_documents["kpi"]["kpi_version"],
            "problem": lineage_documents["problem"],
            "snapshot": {
                "snapshot_version": lineage_documents["snapshot"][
                    "snapshot_version"
                ],
                "snapshot_hash": lineage_documents["snapshot"]["snapshot_hash"],
            },
            "solution_version": lineage_documents["solution"][
                "planning_solution_version"
            ],
            "solver_report_version": lineage_documents["solver_report"][
                "solver_report_version"
            ],
            "validation_report": {
                "validation_report_version": lineage_documents[
                    "validation_report"
                ]["validation_report_version"],
                "status": lineage_documents["validation_report"]["status"],
            },
        },
        "rejections": checks[
            "validator-fail-mixed-lineage-and-tamper-rejections"
        ]["details"],
        "atomicity": checks[
            "atomic-write-exact-replay-and-partial-cleanup"
        ]["details"],
        "state_boundary": checks[
            "p2-internal-non-publishable-state-and-deferred-boundary"
        ]["details"],
        "boundaries": report["boundaries"],
    }


def _stable_fingerprints(replay: JsonObject) -> JsonObject:
    correctness = _sha256(_stable_correctness_projection(replay["correctness"]))
    benchmark_hashes = {
        size: _sha256(
            _stable_benchmark_projection(replay["benchmarks"][size])
        )
        for size in _EXPECTED_BENCHMARK_SIZES
    }
    output = _sha256(_stable_output_projection(replay["export"]))
    combined = _sha256(
        {
            "projection_version": SEMANTIC_PROJECTION_VERSION,
            "correctness": correctness,
            "benchmarks": benchmark_hashes,
            "export": output,
        }
    )
    return {
        "projection_version": SEMANTIC_PROJECTION_VERSION,
        "correctness": correctness,
        "benchmarks": benchmark_hashes,
        "export": output,
        "combined": combined,
    }


def run_exit_rejection_checks() -> list[JsonObject]:
    """Exercise four stable public unsupported/invalid/limit boundaries."""

    rows: list[JsonObject] = []
    try:
        require_v1_capability_contract([CapabilityName.SECONDARY_CAPACITY])
    except CapabilityContractError as error:
        rows.append(
            {
                "case_id": "UNSUPPORTED_CAPABILITY",
                "status": "PASS",
                "behavior": "REJECTED_BEFORE_PLANNING",
                "category": error.category.value,
                "code": error.code.value,
                "details": {"capabilities": list(error.capability_names)},
            }
        )
    else:
        _fail("rejection_cases.UNSUPPORTED_CAPABILITY", "capability was accepted")

    invalid_problem = ImmutablePlanningProblemV2(
        canonical_bytes=b"{}",
        problem_hash=f"sha256:{'0' * 64}",
        snapshot_id="SNAPSHOT-P2-GATE-INVALID",
        problem_builder_version="planning-problem-builder.v2",
    )
    try:
        verify_problem_v2(invalid_problem)
    except PlanningProblemError as error:
        rows.append(
            {
                "case_id": "INVALID_PLANNING_PROBLEM",
                "status": "PASS",
                "behavior": "REJECTED_BEFORE_SOLVER",
                "category": error.category.value,
                "code": error.code.value,
                "details": {
                    "field": error.field,
                    "expected_contract": error.expected_contract,
                },
            }
        )
    else:
        _fail("rejection_cases.INVALID_PLANNING_PROBLEM", "Problem was accepted")

    valid_limits = simulation_solve_limits(
        limits_id="LIMITS-P2-GATE-NEGATIVE",
        limits_revision="1.0.0",
        source_record_id="LIMITS-P2-GATE-NEGATIVE",
        max_wall_time_seconds=1.0,
        max_workers=1,
        random_seed=20260821,
    )
    invalid_limits = cast(JsonObject, dict(valid_limits))
    invalid_limits["max_wall_time_seconds"] = 0.0
    try:
        validate_solve_limits(invalid_limits)
    except PlanningContractError as error:
        rows.append(
            {
                "case_id": "INVALID_SOLVE_LIMITS",
                "status": "PASS",
                "behavior": "REJECTED_BEFORE_SOLVER",
                "category": error.category.value,
                "code": error.code.value,
                "details": {
                    "reason": error.reason.value,
                    "field": error.field,
                    "expected_contract": error.expected_contract,
                },
            }
        )
    else:
        _fail("rejection_cases.INVALID_SOLVE_LIMITS", "zero limit was accepted")

    unknown = outcome_for_solver_status(SolverStatus.UNKNOWN)
    outcome_document = outcome_document_for_status(SolverStatus.UNKNOWN)
    product_error = outcome_document["product_error"]
    if (
        unknown.candidate_available
        or outcome_document["state"] != "NO_SOLUTION_WITHIN_LIMIT"
        or product_error is None
        or product_error["category"] != "NO_SOLUTION_WITHIN_LIMIT"
        or product_error["code"] != "NO_SOLUTION_WITHIN_LIMIT"
    ):
        _fail(
            "rejection_cases.NO_SOLUTION_WITHIN_LIMIT",
            "UNKNOWN status mapping is not fail-closed",
        )
    rows.append(
        {
            "case_id": "NO_SOLUTION_WITHIN_LIMIT",
            "status": "PASS",
            "behavior": "NO_CANDIDATE_AND_NOT_INFEASIBLE",
            "category": product_error["category"],
            "code": product_error["code"],
            "details": {
                "solver_status": SolverStatus.UNKNOWN.value,
                "planning_run_state": outcome_document["state"],
                "candidate_available": unknown.candidate_available,
            },
        }
    )
    _validate_rejection_cases(rows)
    return rows


def _validate_rejection_cases(rows: Sequence[Mapping[str, object]]) -> None:
    if tuple(row.get("case_id") for row in rows) != _EXPECTED_REJECTION_IDS:
        _fail("rejection_cases", "rejection case identity/order changed")
    expected = {
        "UNSUPPORTED_CAPABILITY": (
            "UNSUPPORTED_CAPABILITY",
            "UNSUPPORTED_CAPABILITY",
        ),
        "INVALID_PLANNING_PROBLEM": ("MODEL_INVALID", "MODEL_INVALID"),
        "INVALID_SOLVE_LIMITS": ("MODEL_INVALID", "MODEL_INVALID"),
        "NO_SOLUTION_WITHIN_LIMIT": (
            "NO_SOLUTION_WITHIN_LIMIT",
            "NO_SOLUTION_WITHIN_LIMIT",
        ),
    }
    for index, row in enumerate(rows):
        case_id = cast(str, row["case_id"])
        if row.get("status") != "PASS" or (
            row.get("category"),
            row.get("code"),
        ) != expected[case_id]:
            _fail(
                f"rejection_cases[{index}]",
                "unsupported/invalid/limit mapping changed",
            )


def _run_stage(stage: str, operation: Any) -> Any:
    try:
        return operation()
    except (P2GateContractError, P2GateExecutionError):
        raise
    except Exception as error:
        raise P2GateExecutionError(stage, error) from error


def _run_replay(root: Path, index: int, code_commit: str) -> JsonObject:
    replay_started = perf_counter()
    stage_seconds: JsonObject = {}

    started = perf_counter()
    correctness = cast(
        JsonObject,
        _run_stage(
            f"replay-{index}.correctness",
            lambda: run_correctness_checks(root),
        ),
    )
    stage_seconds["correctness"] = round(perf_counter() - started, 9)
    _validate_correctness_report(correctness, code_commit)

    benchmarks: JsonObject = {}
    for size in _EXPECTED_BENCHMARK_SIZES:
        started = perf_counter()
        report = cast(
            JsonObject,
            _run_stage(
                f"replay-{index}.benchmark-{size.lower()}",
                lambda size=size: run_benchmark(
                    root=root, profile_name=size.lower()
                ),
            ),
        )
        stage_seconds[f"benchmark_{size.lower()}"] = round(
            perf_counter() - started, 9
        )
        _validate_benchmark_report(report, size=size, code_commit=code_commit)
        benchmarks[size] = report

    started = perf_counter()
    output = cast(
        JsonObject,
        _run_stage(
            f"replay-{index}.export",
            lambda: run_output_contract_checks(root),
        ),
    )
    stage_seconds["export"] = round(perf_counter() - started, 9)
    _validate_output_report(output, code_commit)

    replay: JsonObject = {
        "replay_index": index,
        "status": "PASS",
        "stage_order": ["correctness", "benchmark_xs", "benchmark_s", "benchmark_m", "export"],
        "stage_seconds": stage_seconds,
        "total_seconds": round(perf_counter() - replay_started, 9),
        "correctness": correctness,
        "benchmarks": benchmarks,
        "export": output,
    }
    replay["stable_fingerprints"] = _stable_fingerprints(replay)
    return replay


def _pass(name: str, details: object) -> JsonObject:
    return {"name": name, "status": "PASS", "details": details}


def _aggregate_checks(
    replays: list[JsonObject], rejection_cases: list[JsonObject]
) -> list[JsonObject]:
    first = replays[0]
    first_correctness_checks = _checks_by_name(first["correctness"], "correctness")
    scenario_rows = first_correctness_checks[
        "formal-ingress-snapshot-problem-replay"
    ]["details"]
    mutation_rows = first_correctness_checks[
        "formula-free-exact-c001-c011-validator-mutations"
    ]["details"]
    benchmark_details = {
        size: {
            "problem_hash": first["benchmarks"][size]["problem"]["problem_hash"],
            "snapshot_hash": first["benchmarks"][size]["problem"]["snapshot_hash"],
            "status": first["benchmarks"][size]["global_solver"]["status"],
            "validator": first["benchmarks"][size]["global_solver"][
                "validation"
            ],
            "model_metrics": first["benchmarks"][size]["global_solver"][
                "model_metrics"
            ],
            "quality": first["benchmarks"][size]["global_solver"]["quality"],
            "timings": first["benchmarks"][size]["global_solver"]["timings"],
            "memory_peak_mb": first["benchmarks"][size]["global_solver"][
                "memory_peak_mb"
            ],
        }
        for size in _EXPECTED_BENCHMARK_SIZES
    }
    package_details = {
        index + 1: _checks_by_name(replay["export"], "export")[
            "deterministic-package-bytes-file-hashes-and-row-counts"
        ]["details"]
        for index, replay in enumerate(replays)
    }
    fingerprints = [
        replay["stable_fingerprints"]["combined"] for replay in replays
    ]
    return [
        _pass(
            _EXPECTED_CHECKS[0],
            {
                "chain": [
                    "Snapshot",
                    "PlanningProblemV2",
                    "PlanningPolicy/SolveLimits",
                    "GlobalCpSatStrategy",
                    "IndependentValidator",
                    "KPI/SolverReport",
                    "InternalExport",
                ],
                "public_boundary_only": True,
            },
        ),
        _pass(
            _EXPECTED_CHECKS[1],
            {
                "repeat_count": len(replays),
                "all_replay_statuses": [replay["status"] for replay in replays],
                "stage_order": first["stage_order"],
            },
        ),
        _pass(
            _EXPECTED_CHECKS[2],
            {
                "scenario_ids": [row["scenario_id"] for row in scenario_rows],
                "scenario_count": len(scenario_rows),
                "problem_hashes": [row["problem_hash"] for row in scenario_rows],
            },
        ),
        _pass(
            _EXPECTED_CHECKS[3],
            {
                "constraint_ids": [row["constraint_id"] for row in mutation_rows],
                "positive_count": 11,
                "negative_count": len(mutation_rows),
            },
        ),
        _pass(
            _EXPECTED_CHECKS[4],
            {
                "profiles": list(_EXPECTED_BENCHMARK_SIZES),
                "profile_executions": len(replays) * 3,
                "global_plus_reference_per_profile": 6,
                "evidence": benchmark_details,
            },
        ),
        _pass(
            _EXPECTED_CHECKS[5],
            {
                "correctness_validator_passes": len(replays) * 7,
                "benchmark_global_validator_passes": len(replays) * 3 * 3,
                "benchmark_reference_validator_passes": len(replays) * 3 * 5 * 3,
                "validator_status": "PASS",
            },
        ),
        _pass(
            _EXPECTED_CHECKS[6],
            {
                "profiles": benchmark_details,
                "unknown_mapping": rejection_cases[3],
            },
        ),
        _pass(
            _EXPECTED_CHECKS[7],
            {
                "explicit_output_contract_executions": len(replays),
                "benchmark_embedded_export_executions": len(replays) * 3,
                "packages": package_details,
            },
        ),
        _pass(
            _EXPECTED_CHECKS[8],
            {
                "case_ids": [row["case_id"] for row in rejection_cases],
                "case_count": len(rejection_cases),
            },
        ),
        _pass(
            _EXPECTED_CHECKS[9],
            {
                "projection_version": SEMANTIC_PROJECTION_VERSION,
                "combined_fingerprints": fingerprints,
                "unique_fingerprints": len(set(fingerprints)),
                "run_specific_hash_policy": (
                    "COLLECTED_BUT_NOT_COMPARED_WHEN_SOLVER_REPORT_TIMING_"
                    "OR_GENERATED_AT_IS_IN_THE_HASH"
                ),
            },
        ),
        _pass(_EXPECTED_CHECKS[10], _BOUNDARIES),
    ]


def run_p2_vertical_slice_gate(*, root: Path, repeat: int = 2) -> JsonObject:
    """Run at least two complete P2 public-boundary replays and aggregate them."""

    if isinstance(repeat, bool) or not isinstance(repeat, int) or repeat < 2:
        _fail("repeat", "P2 Gate requires at least two complete replays")
    root = root.resolve()
    code_commit = _code_commit()
    replays = [
        _run_replay(root, index, code_commit) for index in range(1, repeat + 1)
    ]
    rejection_cases = cast(
        list[JsonObject],
        _run_stage("exit-rejection-contracts", run_exit_rejection_checks),
    )
    checks = _aggregate_checks(replays, rejection_cases)
    combined = [replay["stable_fingerprints"]["combined"] for replay in replays]
    correctness_hashes = [
        replay["stable_fingerprints"]["correctness"] for replay in replays
    ]
    benchmark_hashes = {
        size: [
            replay["stable_fingerprints"]["benchmarks"][size]
            for replay in replays
        ]
        for size in _EXPECTED_BENCHMARK_SIZES
    }
    output_hashes = [replay["stable_fingerprints"]["export"] for replay in replays]
    if (
        len(set(combined)) != 1
        or len(set(correctness_hashes)) != 1
        or len(set(output_hashes)) != 1
        or any(len(set(values)) != 1 for values in benchmark_hashes.values())
    ):
        _fail(
            "hash_consistency",
            "stable business semantics changed across complete Gate replays",
        )

    report: JsonObject = {
        "report_version": REPORT_VERSION,
        "status": "PASS",
        "task_id": TASK_ID,
        "code_commit": code_commit,
        "generated_at_utc": _generated_at(),
        "versions": {
            "gate_contract": REPORT_VERSION,
            "semantic_projection": SEMANTIC_PROJECTION_VERSION,
            "correctness_report": "p2-correctness-report.v1",
            "benchmark_report": "benchmark-report.v1",
            "output_report": "p2-output-contract-report.v1",
            "schema_set": "2.5.0",
        },
        "repeat_count": repeat,
        "execution": {
            "minimum_repeat_count": 2,
            "full_replays_complete": repeat,
            "all_public_boundaries_reexecuted": True,
            "stage_order": replays[0]["stage_order"],
        },
        "replays": replays,
        "rejection_cases": rejection_cases,
        "hash_consistency": {
            "projection_version": SEMANTIC_PROJECTION_VERSION,
            "status": "PASS",
            "combined_fingerprints": combined,
            "correctness_fingerprints": correctness_hashes,
            "benchmark_fingerprints": benchmark_hashes,
            "export_fingerprints": output_hashes,
            "unique_combined_fingerprints": len(set(combined)),
            "run_specific_hash_policy": (
                "FULL_REPORT_EXPORT_KPI_AND_SOLVER_REPORT_HASHES_ARE_COLLECTED_"
                "PER_REPLAY;_ONLY_THE_VERSIONED_TIMING_INDEPENDENT_BUSINESS_"
                "PROJECTION_MUST_MATCH"
            ),
        },
        "checks": checks,
        "check_count": len(checks),
        "counts": {
            "full_replays": repeat,
            "correctness_scenario_executions": repeat * 7,
            "correctness_validator_passes": repeat * 7,
            "correctness_mutation_executions": repeat * 11,
            "unique_constraint_ids": 11,
            "benchmark_profile_executions": repeat * 3,
            "benchmark_global_measured_runs": repeat * 3 * 3,
            "benchmark_reference_measured_runs": repeat * 3 * 5 * 3,
            "benchmark_validator_passes": repeat * 3 * 6 * 3,
            "explicit_output_contract_executions": repeat,
            "embedded_benchmark_export_executions": repeat * 3,
            "rejection_cases": 4,
        },
        "blocking_gaps": [],
        "boundaries": dict(_BOUNDARIES),
    }
    validate_p2_vertical_slice_report(report)
    return report


def validate_p2_vertical_slice_report(report: Mapping[str, object]) -> None:
    """Validate the strict internal ``p2-vertical-slice-report.v1`` contract."""

    expected_keys = {
        "report_version",
        "status",
        "task_id",
        "code_commit",
        "generated_at_utc",
        "versions",
        "repeat_count",
        "execution",
        "replays",
        "rejection_cases",
        "hash_consistency",
        "checks",
        "check_count",
        "counts",
        "blocking_gaps",
        "boundaries",
    }
    _exact_keys(report, expected_keys, "$")
    if report["report_version"] != REPORT_VERSION:
        _fail("report_version", f"expected {REPORT_VERSION}")
    if report["status"] != "PASS" or report["task_id"] != TASK_ID:
        _fail("status/task_id", "Gate report is not a successful TASK-P2-13 report")
    code_commit = report["code_commit"]
    if code_commit != "uncommitted" and not (
        isinstance(code_commit, str)
        and len(code_commit) == 40
        and all(character in "0123456789abcdef" for character in code_commit)
    ):
        _fail("code_commit", "expected uncommitted or a full lowercase Git SHA")
    repeat = report["repeat_count"]
    if isinstance(repeat, bool) or not isinstance(repeat, int) or repeat < 2:
        _fail("repeat_count", "must be an integer >= 2")
    replays = _items(report["replays"], "replays")
    if len(replays) != repeat:
        _fail("replays", "replay count does not match repeat_count")

    recomputed: list[JsonObject] = []
    for index, raw_replay in enumerate(replays):
        replay = _object(raw_replay, f"replays[{index}]")
        if replay.get("replay_index") != index + 1 or replay.get("status") != "PASS":
            _fail(f"replays[{index}]", "replay identity/status is invalid")
        correctness = _object(replay.get("correctness"), f"replays[{index}].correctness")
        _validate_correctness_report(correctness, cast(str, code_commit))
        benchmarks = _object(replay.get("benchmarks"), f"replays[{index}].benchmarks")
        if set(benchmarks) != set(_EXPECTED_BENCHMARK_SIZES):
            _fail(f"replays[{index}].benchmarks", "expected exact XS/S/M reports")
        for size in _EXPECTED_BENCHMARK_SIZES:
            _validate_benchmark_report(
                _object(benchmarks[size], f"replays[{index}].benchmarks.{size}"),
                size=size,
                code_commit=cast(str, code_commit),
            )
        output = _object(replay.get("export"), f"replays[{index}].export")
        _validate_output_report(output, cast(str, code_commit))
        stable = _stable_fingerprints(replay)
        if replay.get("stable_fingerprints") != stable:
            _fail(f"replays[{index}].stable_fingerprints", "fingerprint mismatch")
        recomputed.append(stable)

    rejection_cases = _items(report["rejection_cases"], "rejection_cases")
    _validate_rejection_cases(
        [_object(row, f"rejection_cases[{index}]") for index, row in enumerate(rejection_cases)]
    )
    combined = [value["combined"] for value in recomputed]
    if len(set(combined)) != 1:
        _fail("hash_consistency", "combined semantic hashes differ")
    consistency = _object(report["hash_consistency"], "hash_consistency")
    if (
        consistency.get("status") != "PASS"
        or consistency.get("projection_version") != SEMANTIC_PROJECTION_VERSION
        or consistency.get("combined_fingerprints") != combined
        or consistency.get("unique_combined_fingerprints") != 1
    ):
        _fail("hash_consistency", "aggregate hash evidence is inconsistent")

    checks = _checks_by_name(report, "$")
    if tuple(checks) != _EXPECTED_CHECKS:
        _fail("checks", "Gate check identity/order changed")
    if report["check_count"] != len(_EXPECTED_CHECKS):
        _fail("check_count", "Gate check count changed")
    if report["blocking_gaps"] != []:
        _fail("blocking_gaps", "PASS Gate report cannot contain blocking gaps")
    if report["boundaries"] != _BOUNDARIES:
        _fail("boundaries", "phase/Exit/Production boundary changed")
    serialized = json.dumps(report, sort_keys=True)
    if '"exit_gate_decision": "READY"' in serialized or '"p3": "STARTED"' in serialized:
        _fail("boundaries", "TASK-P2-13 cannot make an Exit or P3 decision")


def _failure_report(error: Exception, repeat: int) -> JsonObject:
    stage = getattr(error, "stage", "orchestrator")
    return {
        "report_version": REPORT_VERSION,
        "status": "FAIL",
        "task_id": TASK_ID,
        "code_commit": _code_commit(),
        "generated_at_utc": _generated_at(),
        "repeat_count": repeat,
        "error": {
            "stage": stage,
            "error_type": type(error).__name__,
            "message": str(error),
        },
        "blocking_gaps": [
            {
                "gap_id": "P2-GATE-EXECUTION-001",
                "stage": stage,
                "status": "BLOCKING",
                "remediation": "REQUIRES_SEPARATE_BOUNDED_TASK",
            }
        ],
        "boundaries": dict(_BOUNDARIES),
    }


def _write_report(path: Path, report: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--repeat", type=int, default=2)
    parser.add_argument("--report", type=Path, required=True)
    arguments = parser.parse_args(argv)
    try:
        report = run_p2_vertical_slice_gate(
            root=arguments.root,
            repeat=arguments.repeat,
        )
    except Exception as error:
        report = _failure_report(error, arguments.repeat)
        exit_code = 1
    else:
        exit_code = 0
    _write_report(arguments.report, report)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "REPORT_VERSION",
    "SEMANTIC_PROJECTION_VERSION",
    "TASK_ID",
    "P2GateContractError",
    "P2GateExecutionError",
    "main",
    "run_exit_rejection_checks",
    "run_p2_vertical_slice_gate",
    "validate_p2_vertical_slice_report",
]
