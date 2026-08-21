"""Reproducible dependency, container, and phase-aware CI contract checks."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any, cast

import yaml

from app.planning.backends.cp_sat.contract_check import (
    main as backend_contract_main,
)
from app.planning.backends.cp_sat.core_model_check import main as core_model_main
from app.planning.backends.cp_sat.fact_lock_model_check import (
    main as fact_lock_model_main,
)
from app.planning.backends.cp_sat.objective_strategy_check import (
    main as objective_strategy_main,
)
from app.planning.backends.cp_sat.temporal_model_check import (
    main as temporal_model_main,
)
from app.planning.problem.contract_check import main as problem_contract_main
from app.planning.policy.contract_check import main as machine_contract_main
from app.planning.validation.problem_validator_check import (
    main as formal_validator_main,
)

ROOT = Path(__file__).resolve().parents[3]

EXPECTED_RUNTIME_DEPENDENCIES = {
    "alembic==1.16.5",
    "celery==5.5.3",
    "defusedxml==0.7.1",
    "fastapi==0.116.1",
    "openpyxl==3.1.5",
    "opentelemetry-api==1.36.0",
    "ortools==9.15.6755",
    "psycopg[binary]==3.2.9",
    "pydantic-settings==2.10.1",
    "redis==6.4.0",
    "sqlalchemy==2.0.43",
    "structlog==25.4.0",
    "uvicorn==0.35.0",
}
PHASE_GOVERNANCE_TEST_ID = "TEST-PHASE-GOVERNANCE-001"


def test_runtime_dependencies_are_exact_and_solver_is_exact_pinned() -> None:
    project = cast(
        dict[str, Any],
        tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8")),
    )
    dependencies = set(cast(list[str], project["project"]["dependencies"]))
    assert dependencies == EXPECTED_RUNTIME_DEPENDENCIES
    lock_text = (ROOT / "uv.lock").read_text(encoding="utf-8").lower()
    assert 'name = "ortools"' in lock_text
    assert 'version = "9.15.6755"' in lock_text
    assert "cp312-cp312-win_amd64" in lock_text
    assert "cp312-cp312-manylinux_2_27_x86_64" in lock_text


def test_compose_has_health_checked_development_services_and_no_prod_defaults() -> None:
    compose = cast(
        dict[str, Any],
        yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8")),
    )
    services = cast(dict[str, Any], compose["services"])
    assert set(services) == {"api", "database", "redis", "worker"}
    assert services["database"]["image"] == "postgres:17.6-alpine3.22"
    assert services["redis"]["image"] == "redis:8.2.1-alpine3.22"
    for service in ("database", "redis", "api"):
        assert "healthcheck" in services[service]
    api_environment = services["api"]["environment"]
    assert api_environment["PLANTNEXUS_DATA_PLANE"] == "development"
    assert api_environment["PLANTNEXUS_RUNTIME_ENVIRONMENT"] == "development"
    assert api_environment["PLANTNEXUS_SIMULATION_API_ENABLED"] == "false"
    assert (
        "PLANTNEXUS_POSTGRES_PASSWORD"
        in services["database"]["environment"]["POSTGRES_PASSWORD"]
    )


def test_example_environment_is_explicitly_non_production() -> None:
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "PLANTNEXUS_RUNTIME_ENVIRONMENT=development" in example
    assert "PLANTNEXUS_DATA_PLANE=development" in example
    assert "PLANTNEXUS_SIMULATION_API_ENABLED=false" in example
    assert "replace-me-local-only" in example
    assert "production" not in "\n".join(
        line for line in example.splitlines() if not line.startswith("#")
    )


def test_ci_runs_repository_gates_and_discovers_the_current_task() -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    normalized_workflow = " ".join(workflow.split())
    required_fragments = (
        "name: PlantNexus repository gates",
        "uv sync --locked",
        "uv run ruff check .",
        "uv run pyright backend/app backend/tests",
        "backend/tests/integration",
        "backend/tests/property",
        "app.application.p1_gate_report",
        "--scenario fixtures/synthetic/SIM-P1-INGRESS-001",
        "--repeat 2",
        "build/validation/ci-p1-data-pipeline.json",
        "app.planning.problem.contract_check",
        "build/validation/ci-planning-problem-contracts.json",
        "app.planning.policy.contract_check",
        "build/validation/ci-planning-machine-contracts.json",
        "app.planning.backends.cp_sat.contract_check",
        "build/validation/ci-solver-backend-foundation.json",
        "app.planning.validation.problem_validator_check",
        "build/validation/ci-formal-schedule-validator.json",
        "app.planning.backends.cp_sat.core_model_check",
        "build/validation/ci-cp-sat-core-model.json",
        "app.planning.backends.cp_sat.temporal_model_check",
        "build/validation/ci-cp-sat-temporal-model.json",
        "app.planning.backends.cp_sat.fact_lock_model_check",
        "build/validation/ci-cp-sat-fact-lock-model.json",
        "app.planning.backends.cp_sat.objective_strategy_check",
        "build/validation/ci-objective-strategy.json",
        "app.infrastructure.contract_check",
        "docker compose --env-file .env.example config --quiet",
        "PLANTNEXUS_CI_CHANGE_BASE:",
        "github.event.pull_request.base.sha || github.event.before",
        "--discover-task-from",
        "build/traceability/ci-current-task-report.json",
        "uv build",
        "PLANTNEXUS_BENCHMARK_PROFILE: pr",
    )
    for fragment in required_fragments:
        assert fragment in workflow
    assert "scripts/run_benchmark.py" in workflow
    assert "actions/upload-artifact@v4" in workflow
    assert "name: P1 common ingress gate" in workflow
    assert workflow.count("uv run python scripts/check_docs.py") == 2
    assert (
        "uv run python scripts/check_docs.py --discover-task-from "
        '"${PLANTNEXUS_CI_CHANGE_BASE}" --check-diff '
        "--report build/traceability/ci-current-task-report.json"
    ) in normalized_workflow
    assert "plantnexus-ci-evidence-${{ github.run_id }}" in workflow
    assert "if: always()" in workflow
    assert "continue-on-error" not in workflow
    assert "TASK-P0-10" not in workflow
    assert "TASK-P0-08" not in workflow
    assert "docs/tasks/P0/" not in workflow
    assert PHASE_GOVERNANCE_TEST_ID == "TEST-PHASE-GOVERNANCE-001"


def test_ci_planning_problem_contract_report_is_machine_checkable(
    tmp_path: Path,
) -> None:
    report_path = tmp_path / "planning-problem-contracts.json"
    assert (
        problem_contract_main(["--root", str(ROOT), "--report", str(report_path)]) == 0
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))

    assert report["report_version"] == "planning-problem-contract-report.v1"
    assert report["status"] == "PASS"
    assert report["task_id"] == "TASK-P2-01"
    assert report["schema_set_version"] == "2.4.0"
    assert report["check_count"] == 4
    assert {check["name"] for check in report["checks"]} == {
        "v1-byte-preservation",
        "v1-schema-sample-replay",
        "v2-schema-sample-replay",
        "v2-gap-closure-fields",
    }
    assert report["boundaries"]["v1_default_api"] == "PRESERVED"
    assert report["boundaries"]["v2_api"] == "OPT_IN"
    assert report["boundaries"]["solver"] == "NOT_IMPLEMENTED_BY_TASK"


def test_ci_planning_machine_contract_report_is_machine_checkable(
    tmp_path: Path,
) -> None:
    report_path = tmp_path / "planning-machine-contracts.json"
    assert (
        machine_contract_main(["--root", str(ROOT), "--report", str(report_path)]) == 0
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))

    assert report["report_version"] == "planning-machine-contract-report.v1"
    assert report["status"] == "PASS"
    assert report["task_id"] == "TASK-P2-02"
    assert report["schema_set_version"] == "2.4.0"
    assert report["check_count"] == 5
    assert {check["name"] for check in report["checks"]} == {
        "fixed-schema-and-sample-artifacts",
        "planning-policy-and-solve-limits",
        "seven-status-product-mapping",
        "cross-document-fingerprint-and-replay",
        "task-boundary",
    }
    assert report["boundaries"]["sample_solver_execution"] == "NONE"
    assert report["boundaries"]["p2_objective_scope"] == "OBJ-001_ONLY"
    assert report["boundaries"]["solver_backend"] == "NOT_IMPLEMENTED_BY_TASK"
    assert report["boundaries"]["schedule_validator"] == "NOT_IMPLEMENTED_BY_TASK"


def test_ci_solver_backend_foundation_report_is_machine_checkable(
    tmp_path: Path,
) -> None:
    report_path = tmp_path / "solver-backend-foundation.json"
    assert (
        backend_contract_main(["--root", str(ROOT), "--report", str(report_path)]) == 0
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))

    assert report["report_version"] == "solver-backend-foundation-report.v1"
    assert report["status"] == "PASS"
    assert report["task_id"] == "TASK-P2-03"
    assert report["check_count"] == 6
    assert {check["name"] for check in report["checks"]} == {
        "exact-dependency-and-lock",
        "solver-identity-and-platform",
        "namespace-and-protocol-boundary",
        "seven-status-adapter-contract",
        "solve-limits-parameter-capture",
        "engineering-smoke-and-serialization-isolation",
    }
    assert report["boundaries"]["business_constraints"] == (
        "CORE_P2_05_TEMPORAL_P2_06_FACT_LOCK_P2_07_PRESENT"
    )
    assert report["boundaries"]["candidate_solution"] == (
        "P2_07_COMPATIBILITY_AND_P2_08_GLOBAL_STRATEGY"
    )
    assert report["boundaries"]["schedule_validator"] == "TASK_P2_04_PRESENT"
    assert report["boundaries"]["business_feasibility"] == (
        "EVALUATED_BY_TASK_P2_05_THROUGH_P2_08_NOT_FOUNDATION_SMOKES"
    )
    assert report["boundaries"]["benchmark"] == "NOT_APPLICABLE_FOUNDATION_ONLY"


def test_ci_cp_sat_core_model_report_is_machine_checkable(tmp_path: Path) -> None:
    report_path = tmp_path / "cp-sat-core-model.json"
    assert core_model_main(["--root", str(ROOT), "--report", str(report_path)]) == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))

    assert report["report_version"] == "cp-sat-core-model-report.v1"
    assert report["status"] == "PASS"
    assert report["task_id"] == "TASK-P2-05"
    assert report["check_count"] == 6
    assert report["counts"] == {
        "core_constraint_ids": 5,
        "candidate_cases": 2,
        "infeasible_cases": 1,
        "precheck_rejections": 2,
        "validator_mutations": 2,
        "brute_force_cases": 4,
    }
    assert report["boundaries"] == {
        "problem_policy_solution_schema_changes": "NONE",
        "constraint_rule_changes": "NONE",
        "formal_validator_changes": "NONE",
        "dependency_changes": "NONE",
        "implemented_constraints": [
            "C-001",
            "C-003",
            "C-004",
            "C-010",
            "C-011",
        ],
        "deferred_constraints": [
            "C-002",
            "C-005",
            "C-006",
            "C-007",
            "C-008",
            "C-009",
        ],
        "objective": "POSTSOLVE_MEASUREMENT_ONLY_NOT_OPTIMIZED",
        "strategy": "NOT_IMPLEMENTED",
        "benchmark": "TINY_CORRECTNESS_ONLY_NO_XS_S_M_BASELINE",
        "candidate_publishability": "TEST_ARTIFACT_ONLY",
        "production_readiness": "NOT_CLAIMED",
    }


def test_ci_cp_sat_temporal_model_report_is_machine_checkable(
    tmp_path: Path,
) -> None:
    report_path = tmp_path / "cp-sat-temporal-model.json"
    assert (
        temporal_model_main(["--root", str(ROOT), "--report", str(report_path)])
        == 0
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))

    assert report["report_version"] == "cp-sat-temporal-model-report.v1"
    assert report["status"] == "PASS"
    assert report["task_id"] == "TASK-P2-06"
    assert report["check_count"] == 7
    assert report["counts"] == {
        "temporal_constraint_ids": 4,
        "candidate_cases": 5,
        "infeasible_cases": 3,
        "precheck_rejections": 2,
        "validator_mutations": 4,
        "tiny_oracle_cases": 8,
    }
    assert {check["name"] for check in report["checks"]} == {
        "fixed-contract-builder-validator-rule-and-lock-fingerprints",
        "exact-signed-rounding-and-half-open-calendar-projection",
        "c002-c005-c006-c009-positive-candidates",
        "max-lag-calendar-gate-infeasible-and-precheck-boundaries",
        "independent-validator-temporal-mutations",
        "tiny-exact-window-oracle",
        "model-delta-and-real-telemetry",
    }
    assert report["boundaries"]["implemented_constraints"] == [
        "C-001",
        "C-002",
        "C-003",
        "C-004",
        "C-005",
        "C-006",
        "C-009",
        "C-010",
        "C-011",
    ]
    assert report["boundaries"]["deferred_constraints"] == ["C-007", "C-008"]
    assert report["boundaries"]["formal_validator_changes"] == "NONE"
    assert report["boundaries"]["objective"] == (
        "POSTSOLVE_MEASUREMENT_ONLY_NOT_OPTIMIZED"
    )
    assert report["boundaries"]["benchmark"] == (
        "MODEL_DELTA_ONLY_NO_XS_S_M_BASELINE"
    )


def test_ci_cp_sat_fact_lock_model_report_is_machine_checkable(
    tmp_path: Path,
) -> None:
    report_path = tmp_path / "cp-sat-fact-lock-model.json"
    assert (
        fact_lock_model_main(["--root", str(ROOT), "--report", str(report_path)])
        == 0
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))

    assert report["report_version"] == "cp-sat-fact-lock-model-report.v1"
    assert report["status"] == "PASS"
    assert report["task_id"] == "TASK-P2-07"
    assert report["check_count"] == 7
    assert report["counts"] == {
        "fact_lock_constraint_ids": 2,
        "candidate_cases": 4,
        "infeasible_cases": 3,
        "precheck_rejections": 4,
        "validator_mutations": 2,
        "tiny_oracle_cases": 6,
    }
    assert {check["name"] for check in report["checks"]} == {
        "fixed-contract-builder-validator-rule-adr-and-lock-fingerprints",
        "c007-running-remainder-resource-and-completed-anchor",
        "c008-hard-exact-and-soft-metadata-only",
        "calendar-resource-overlap-and-horizon-certified-infeasible",
        "fact-lock-self-conflict-and-grid-prechecks",
        "independent-validator-c007-c008-mutations",
        "tiny-exact-oracle-model-delta-and-real-telemetry",
    }
    assert report["boundaries"]["implemented_constraints"] == [
        f"C-{index:03d}" for index in range(1, 12)
    ]
    assert report["boundaries"]["deferred_constraints"] == []
    assert report["boundaries"]["formal_validator_changes"] == "NONE"
    assert report["boundaries"]["soft_lock"] == (
        "METADATA_REFERENCE_ONLY_STABILITY_OBJECTIVE_NOT_EXECUTED"
    )
    assert report["boundaries"]["objective"] == (
        "POSTSOLVE_MEASUREMENT_ONLY_NOT_OPTIMIZED"
    )
    assert report["boundaries"]["benchmark"] == (
        "TINY_CORRECTNESS_ONLY_NO_XS_S_M_BASELINE"
    )


def test_ci_objective_strategy_report_is_machine_checkable(tmp_path: Path) -> None:
    report_path = tmp_path / "objective-strategy.json"
    assert (
        objective_strategy_main(
            ["--root", str(ROOT), "--report", str(report_path)]
        )
        == 0
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))

    assert report["report_version"] == "objective-strategy-report.v1"
    assert report["status"] == "PASS"
    assert report["task_id"] == "TASK-P2-08"
    assert report["check_count"] == 7
    assert report["counts"] == {
        "objective_ids": 1,
        "tiny_optimality_cases": 4,
        "independent_validator_passes": 4,
        "certified_infeasible_cases": 1,
        "status_values": 7,
        "production_rejections": 1,
    }
    assert {check["name"] for check in report["checks"]} == {
        "fixed-contract-model-validator-adr-and-lock-fingerprints",
        "approved-versioned-simulation-policy-and-explicit-limits",
        "exact-obj001-model-shape-unit-and-overflow-domain",
        "tiny-brute-force-weighted-tardiness-optimality",
        "complete-hard-domain-and-independent-validator-gate",
        "honest-status-solution-report-limits-and-provenance",
        "global-only-and-production-deferred-boundary",
    }
    assert report["boundaries"] == {
        "hard_constraints": "C-001_THROUGH_C-011_COMPLETE_AND_UNCHANGED",
        "objective": "OBJ-001_ONLY_PRIORITY_WEIGHTED_TARDINESS_SECONDS",
        "strategy": "ONE_GLOBAL_CP_SAT_MODEL_NO_DECOMPOSITION_OR_FALLBACK",
        "policy": "VERSIONED_SIMULATION_ONLY",
        "production_authority": "BLOCKED_BY_OPEN_006_011_012",
        "obj_002_obj_003": "DEFERRED",
        "formal_validator_changes": "NONE",
        "schema_contract_changes": "NONE",
        "dependency_changes": "NONE",
        "benchmark": "TINY_CORRECTNESS_ONLY_NO_XS_S_M_BASELINE",
        "publishability": "INTERNAL_TEST_EVIDENCE_ONLY",
    }


def test_ci_formal_schedule_validator_report_is_machine_checkable(
    tmp_path: Path,
) -> None:
    report_path = tmp_path / "formal-schedule-validator.json"
    assert (
        formal_validator_main(["--root", str(ROOT), "--report", str(report_path)]) == 0
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))

    assert report["report_version"] == "formal-schedule-validator-report.v1"
    assert report["status"] == "PASS"
    assert report["task_id"] == "TASK-P2-04"
    assert report["check_count"] == 6
    assert report["counts"] == {
        "positive_cases": 1,
        "mutation_cases": 13,
        "constraints_covered": 11,
        "required_mutation_classes": 13,
        "hard_violations": 14,
        "property_examples": 6,
    }
    assert {check["name"] for check in report["checks"]} == {
        "fixed-contract-and-fixture-fingerprints",
        "formal-positive-and-status-independence",
        "c001-c011-declarative-mutations",
        "report-error-schema-and-determinism",
        "duration-and-ordering-properties",
        "independent-source-boundary",
    }
    assert report["boundaries"]["backend_constraint_reuse"] == "NONE"
    assert report["boundaries"]["solver_status_trusted"] is False
    assert report["boundaries"]["p0_fixture_and_mutation_bytes"] == "PRESERVED"
    assert report["boundaries"]["cp_sat_business_model"] == "NOT_MODIFIED_BY_TASK"


def test_container_build_is_pinned_and_non_root() -> None:
    dockerfile = (ROOT / "infra" / "Dockerfile").read_text(encoding="utf-8")
    assert dockerfile.startswith("FROM python:3.12.13-slim-bookworm\n")
    assert "uv==0.11.32" in dockerfile
    assert "uv sync --locked --no-dev --no-editable" in dockerfile
    assert "USER plantnexus" in dockerfile
    assert "app.api.app:app" in dockerfile
