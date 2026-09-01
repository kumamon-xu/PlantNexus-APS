#!/usr/bin/env python3
"""Generate TASK-P6-07 Planning ingress and authority-invariant evidence."""

from __future__ import annotations

import argparse
import ast
from copy import deepcopy
from datetime import UTC, datetime
from hashlib import sha256
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time
from typing import Any, Mapping, Sequence, cast


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
for candidate in (ROOT, BACKEND):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from app.duration_prediction.planning_ingress import (  # noqa: E402
    PlanningDurationDecision,
    evaluate_planning_authority_invariants,
)
from app.duration_prediction.runtime import (  # noqa: E402
    DurationCandidate,
    DurationProviderSignal,
)
from app.planning.validation import validate_problem_schedule  # noqa: E402
from backend.tests.p6_planning_integration_support import (  # noqa: E402
    build_integration_problem,
    integration_inputs,
    provider_for_tests,
    solve_problem,
)


type JsonObject = dict[str, Any]

REPORT_VERSION = "p6-planning-integration-report.v1"
TASK_ID = "TASK-P6-07"
DIFF_BASE = "e54e103e9c15cf672d8bcefdfcee5b5775757922"
PRESERVED_OWNER_PATHS = (
    "backend/app/planning/problem/builder.py",
    "backend/app/planning/problem/contracts.py",
    "backend/app/planning/problem/hashing.py",
    "backend/app/planning/backends/cp_sat/backend.py",
    "backend/app/planning/backends/cp_sat/core_constraints.py",
    "backend/app/planning/backends/cp_sat/model.py",
    "backend/app/planning/backends/cp_sat/objectives.py",
    "backend/app/planning/strategies/global_cp_sat.py",
    "backend/app/planning/validation/problem_schedule_validator.py",
    "backend/app/planning/validation/replan_candidate_validator.py",
    "backend/app/application/replan_application.py",
    "backend/app/domain/state_machines/contracts.py",
    "backend/app/domain/state_machines/schedule_version.py",
    "backend/app/domain/state_machines/export_job.py",
    "backend/app/domain/schedule_version.py",
    "backend/app/domain/export_job.py",
)
FORBIDDEN_IMPORT_PREFIXES = (
    "app.api",
    "app.application",
    "app.infrastructure",
    "app.planning.backends",
    "app.planning.validation",
    "ortools",
    "sqlalchemy",
)


class P6PlanningIntegrationReportError(ValueError):
    """A deterministic machine-evidence failure."""


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _digest(value: bytes) -> str:
    return f"sha256:{sha256(value).hexdigest()}"


def _pass(name: str, details: object) -> JsonObject:
    return {"name": name, "status": "PASS", "details": details}


def _base_bytes(root: Path, relative: str) -> bytes:
    completed = subprocess.run(
        ["git", "show", f"{DIFF_BASE}:{relative}"],
        cwd=root,
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise P6PlanningIntegrationReportError(
            f"cannot read Diff-base owner: {relative}"
        )
    return completed.stdout


def _preserved_owners(root: Path) -> list[JsonObject]:
    evidence: list[JsonObject] = []
    for relative in PRESERVED_OWNER_PATHS:
        path = root / relative
        if not path.is_file():
            raise P6PlanningIntegrationReportError(
                f"preserved owner is missing: {relative}"
            )
        current = path.read_bytes()
        base = _base_bytes(root, relative)
        if current != base:
            raise P6PlanningIntegrationReportError(
                f"preserved owner changed: {relative}"
            )
        evidence.append(
            {
                "path": relative,
                "sha256": sha256(current).hexdigest(),
            }
        )
    return evidence


def _module_isolation(root: Path) -> JsonObject:
    relative = "backend/app/duration_prediction/planning_ingress.py"
    source = (root / relative).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imports.update(
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    )
    violations = sorted(
        module
        for module in imports
        if any(
            module == prefix or module.startswith(prefix + ".")
            for prefix in FORBIDDEN_IMPORT_PREFIXES
        )
    )
    if violations:
        raise P6PlanningIntegrationReportError(
            f"planning ingress crossed module boundary: {violations}"
        )
    return {
        "source_sha256": sha256(source.encode("utf-8")).hexdigest(),
        "forbidden_imports": violations,
        "solver_validator_state_or_io_imports": 0,
    }


def _fresh_validation(result: Any, run_id: str) -> JsonObject:
    solved = solve_problem(result, run_id=run_id)
    if solved.validation_report is None:
        raise P6PlanningIntegrationReportError(
            f"{run_id} did not produce formal Validator evidence"
        )
    fresh = validate_problem_schedule(result.problem.document, solved.solution)
    if (
        solved.solution.get("solver_status") not in {"OPTIMAL", "FEASIBLE"}
        or solved.validation_report.get("status") != "PASS"
        or solved.validation_report.get("hard_violation_count") != 0
        or fresh != solved.validation_report
    ):
        raise P6PlanningIntegrationReportError(
            f"{run_id} Solver/fresh Validator boundary failed"
        )
    stage = cast(list[JsonObject], solved.solution["objective_stage_results"])[0]
    return {
        "solver_status": solved.solution["solver_status"],
        "validator_status": fresh["status"],
        "hard_violation_count": fresh["hard_violation_count"],
        "objective_value": stage["objective_value"],
        "problem_hash": result.problem.problem_hash,
    }


def _validator_mutations(accepted: Any) -> list[JsonObject]:
    solved = solve_problem(accepted, run_id="RUN-P6-07-REPORT-MUTATIONS")
    if solved.validation_report is None:
        raise P6PlanningIntegrationReportError("mutation source has no Validator PASS")
    evidence: list[JsonObject] = []
    mutations = (
        ("C-003", "resource_id", "not-a-candidate-resource"),
        (
            "C-010",
            "duration_seconds",
            accepted.lineage[0].standard_duration_seconds,
        ),
    )
    for constraint_id, field_name, value in mutations:
        candidate = deepcopy(solved.solution)
        candidate["assignments"][0][field_name] = value
        report = validate_problem_schedule(accepted.problem.document, candidate)
        observed = {
            str(item["constraint_id"])
            for item in cast(list[JsonObject], report["violations"])
        }
        if report["status"] != "FAIL" or constraint_id not in observed:
            raise P6PlanningIntegrationReportError(
                f"formal Validator did not reject {constraint_id} mutation"
            )
        evidence.append(
            {
                "constraint_id": constraint_id,
                "status": report["status"],
                "hard_violation_count": report["hard_violation_count"],
            }
        )
    return evidence


def _authority_mutations(accepted: Any) -> list[JsonObject]:
    mutations: tuple[tuple[str, Any], ...] = (
        (
            "routing",
            lambda value: value["operation_instances"][0].update(
                {"resource_options": []}
            ),
        ),
        (
            "resource_compatibility",
            lambda value: value["resources"][0]["capabilities"].append(
                "P6-MUTATION"
            ),
        ),
        (
            "hard_constraints",
            lambda value: value["operation_instances"][0].update(
                {"release_at_utc": "2026-08-20T00:01:00Z"}
            ),
        ),
        (
            "operation_state",
            lambda value: value["operation_instances"][0].update(
                {"status": "RUNNING"}
            ),
        ),
        (
            "business_weights",
            lambda value: value["delivery_demands"][0].update(
                {
                    "priority_weight": value["delivery_demands"][0][
                        "priority_weight"
                    ]
                    + 1
                }
            ),
        ),
    )
    evidence: list[JsonObject] = []
    for name, mutate in mutations:
        selected = deepcopy(accepted.problem.document)
        mutate(selected)
        result = evaluate_planning_authority_invariants(
            accepted.standard_problem.document, selected
        )
        if result.as_document()[name]:
            raise P6PlanningIntegrationReportError(
                f"authority invariant accepted mutation: {name}"
            )
        evidence.append({"invariant": name, "rejected": True})
    return evidence


def _percentile_95(samples: Sequence[int]) -> int:
    ordered = sorted(samples)
    index = max(0, (95 * len(ordered) + 99) // 100 - 1)
    return ordered[index]


def _development_comparison(
    snapshot: Any,
    features: Mapping[Any, Mapping[str, Any]],
    provider: Any,
) -> JsonObject:
    warmup = provider.policy.benchmark_warmup_calls
    measured = provider.policy.benchmark_measured_calls
    for _ in range(warmup):
        build_integration_problem(snapshot)
        build_integration_problem(
            snapshot, provider=provider, feature_records=features
        )
    standard_samples: list[int] = []
    enabled_samples: list[int] = []
    for _ in range(measured):
        started = time.perf_counter_ns()
        build_integration_problem(snapshot)
        standard_samples.append(time.perf_counter_ns() - started)
        started = time.perf_counter_ns()
        build_integration_problem(
            snapshot, provider=provider, feature_records=features
        )
        enabled_samples.append(time.perf_counter_ns() - started)
    return {
        "profile_source": "SIM-P6-DURATION-RUNTIME-001@1.0.0",
        "warmup_calls_per_path": warmup,
        "measured_calls_per_path": measured,
        "standard_median_ns": int(statistics.median(standard_samples)),
        "standard_p95_ns": _percentile_95(standard_samples),
        "p6_median_ns": int(statistics.median(enabled_samples)),
        "p6_p95_ns": _percentile_95(enabled_samples),
        "threshold": "OBSERVATION_ONLY_NO_PRODUCTION_SLA",
    }


def run_planning_integration_checks(root: Path) -> JsonObject:
    """Replay every P6-07 path and return sanitized machine evidence."""

    root = root.resolve()
    snapshot, _, features = integration_inputs()
    provider = provider_for_tests()
    standard = build_integration_problem(snapshot)
    accepted = build_integration_problem(
        snapshot, provider=provider, feature_records=features
    )
    low_confidence = build_integration_problem(
        snapshot,
        provider=provider_for_tests(
            candidate_predictor=lambda _model, _feature: DurationCandidate(
                p50_seconds=200,
                p90_seconds=300,
            )
        ),
        feature_records=features,
    )
    unavailable = build_integration_problem(
        snapshot,
        provider=provider_for_tests(
            candidate_predictor=lambda _model, _feature: (_ for _ in ()).throw(
                DurationProviderSignal("PROVIDER_UNAVAILABLE")
            )
        ),
        feature_records=features,
    )
    invalid = build_integration_problem(
        snapshot,
        provider=provider_for_tests(
            candidate_predictor=lambda _model, _feature: DurationCandidate(
                p50_seconds=300,
                p90_seconds=200,
            )
        ),
        feature_records=features,
    )
    replay = build_integration_problem(
        snapshot, provider=provider, feature_records=features
    )

    if standard.problem is not standard.standard_problem:
        raise P6PlanningIntegrationReportError("default-off path changed Problem")
    if any(
        result.problem.canonical_bytes != standard.problem.canonical_bytes
        for result in (low_confidence, unavailable, invalid)
    ):
        raise P6PlanningIntegrationReportError("fallback path changed standard Problem")
    if accepted.lineage[0].decision is not PlanningDurationDecision.MODEL_CANDIDATE:
        raise P6PlanningIntegrationReportError("accepted model candidate was not consumed")
    if (
        accepted.problem.canonical_bytes != replay.problem.canonical_bytes
        or accepted.lineage_documents() != replay.lineage_documents()
    ):
        raise P6PlanningIntegrationReportError("same-input Planning replay drifted")
    invariant_documents = {
        name: value.invariants.as_document()
        for name, value in {
            "standard": standard,
            "accepted": accepted,
            "low_confidence": low_confidence,
            "unavailable": unavailable,
            "invalid": invalid,
        }.items()
    }
    if not all(all(values.values()) for values in invariant_documents.values()):
        raise P6PlanningIntegrationReportError("authority invariant failed")

    solve_evidence = {
        "standard": _fresh_validation(standard, "RUN-P6-07-REPORT-STANDARD"),
        "accepted": _fresh_validation(accepted, "RUN-P6-07-REPORT-ACCEPTED"),
        "fallback": _fresh_validation(
            low_confidence, "RUN-P6-07-REPORT-FALLBACK"
        ),
    }
    authority_mutations = _authority_mutations(accepted)
    validator_mutations = _validator_mutations(accepted)
    preserved = _preserved_owners(root)
    isolation = _module_isolation(root)
    development = _development_comparison(snapshot, features, provider)
    checks = [
        _pass(
            "default-off-standard-problem-byte-identity",
            {
                "problem_hash": standard.problem.problem_hash,
                "lineage_count": len(standard.lineage),
            },
        ),
        _pass(
            "accepted-model-candidate-and-complete-lineage",
            {
                "standard_problem_hash": accepted.standard_problem.problem_hash,
                "selected_problem_hash": accepted.problem.problem_hash,
                "standard_duration_seconds": accepted.lineage[0].standard_duration_seconds,
                "selected_duration_seconds": accepted.lineage[0].selected_duration_seconds,
                "prediction_fingerprint": accepted.lineage[0].prediction_fingerprint,
                "policy_fingerprint": accepted.lineage[0].prediction_policy_fingerprint,
            },
        ),
        _pass(
            "low-unavailable-invalid-exact-standard-fallback",
            {
                "fallback_reasons": [
                    low_confidence.lineage[0].fallback_reason,
                    unavailable.lineage[0].fallback_reason,
                    invalid.lineage[0].fallback_reason,
                ],
                "problem_hash": standard.problem.problem_hash,
            },
        ),
        _pass(
            "same-input-problem-and-lineage-replay",
            {
                "problem_bytes_sha256": _digest(accepted.problem.canonical_bytes),
                "lineage_sha256": _digest(
                    _canonical_bytes(accepted.lineage_documents())
                ),
            },
        ),
        _pass("routing-resource-constraint-state-weight-invariants", invariant_documents),
        _pass("formula-free-authority-mutations", authority_mutations),
        _pass("standard-accepted-fallback-solver-fresh-validator", solve_evidence),
        _pass("formal-validator-c003-c010-mutations", validator_mutations),
        _pass("p2-p4-solver-validator-state-owners-preserved", preserved),
        _pass("planning-ingress-module-isolation", isolation),
        _pass("development-standard-vs-p6-runtime-observation", development),
    ]
    return {
        "report_version": REPORT_VERSION,
        "task_id": TASK_ID,
        "diff_base": DIFF_BASE,
        "code_commit": os.environ.get("PLANTNEXUS_CODE_COMMIT", "uncommitted"),
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "status": "PASS",
        "check_count": len(checks),
        "checks": checks,
        "counts": {
            "ingress_paths": 5,
            "authority_invariants": 7,
            "authority_mutations": len(authority_mutations),
            "fresh_validator_passes": len(solve_evidence),
            "formal_validator_mutations": len(validator_mutations),
            "preserved_owner_files": len(preserved),
        },
        "boundaries": {
            "data_plane": "SIMULATION_TEST_ONLY",
            "default_enabled": False,
            "planning_authority": "ADVISORY_DURATION_ONLY",
            "solver_semantics_changed": False,
            "validator_semantics_changed": False,
            "routing_resource_constraint_state_weight_authority": "UNCHANGED",
            "api_ui_schema_migration_dependency_changes": "NONE",
            "workflow_change": "P4_FROZEN_REPLAY_EXACT_PATH_ISOLATION_ONLY",
            "production_authorized": False,
            "p6_08_plus_started": False,
        },
        "issues": [],
    }


def _write_report(path: Path, report: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--report", type=Path, required=True)
    arguments = parser.parse_args(argv)
    report = run_planning_integration_checks(arguments.root)
    _write_report(arguments.report, report)
    print(
        f"{report['status']} P6 planning integration: "
        f"checks={report['check_count']} "
        f"invariants={report['counts']['authority_invariants']} "
        f"fresh_validator={report['counts']['fresh_validator_passes']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "DIFF_BASE",
    "REPORT_VERSION",
    "TASK_ID",
    "main",
    "run_planning_integration_checks",
]
