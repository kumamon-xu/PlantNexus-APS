"""Reproducible dependency, container, and phase-aware CI contract checks."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any, cast

import yaml

from app.application.p2_gate_report import main as p2_gate_main
from app.application.p3_gate_report import (
    DIFF_BASE as P3_GATE_DIFF_BASE,
    FRONTEND_REPORT_VERSION as P3_FRONTEND_GATE_REPORT_VERSION,
    REPORT_VERSION as P3_GATE_REPORT_VERSION,
)
from app.application.p4_gate_report import (
    DIFF_BASE as P4_GATE_DIFF_BASE,
    FRONTEND_REPORT_VERSION as P4_FRONTEND_GATE_REPORT_VERSION,
    REPORT_VERSION as P4_GATE_REPORT_VERSION,
)
from app.application.p5_portfolio_gate_report import (
    DIFF_BASE as P5_GATE_DIFF_BASE,
    REPORT_VERSION as P5_GATE_REPORT_VERSION,
)
from app.application.p5_exit_gate_audit import (
    DIFF_BASE as P5_EXIT_DIFF_BASE,
    REPORT_VERSION as P5_EXIT_REPORT_VERSION,
)
from app.application.approval_decision_check import main as approval_decision_main
from app.application.publication_check import main as publication_main
from app.application.replan_application_check import (
    main as replan_application_main,
)
from app.application.export_job_check import main as export_job_main
from app.application.execution_fact_projection_check import (
    main as execution_fact_projection_main,
)
from app.application.schedule_version_lifecycle_check import (
    main as schedule_version_lifecycle_main,
)
from app.application.schedule_command_check import main as schedule_command_main
from app.application.workspace_read_model_check import (
    main as workspace_read_model_main,
)
from app.api.planning_workspace_check import main as planning_workspace_api_main
from app.api.replanning_check import main as replanning_api_main
from app.domain.workspace_contract_check import main as workspace_contract_main
from app.domain.execution_contract_check import main as execution_contract_main
from app.exporters.change_report_output_check import (
    main as change_report_output_main,
)
from app.exporters.contract_check import main as output_contract_main
from app.infrastructure.workspace_persistence_check import (
    main as workspace_persistence_main,
)
from app.infrastructure.replan_persistence_check import (
    main as replan_persistence_main,
)
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
from app.planning.backends.cp_sat.replan_solver_check import (
    main as replan_solver_main,
)
from app.planning.backends.cp_sat.temporal_model_check import (
    main as temporal_model_main,
)
from app.planning.problem.contract_check import main as problem_contract_main
from app.planning.problem.freeze_window_check import main as freeze_window_main
from app.planning.policy.contract_check import main as machine_contract_main
from app.planning.reporting.stability_change_report_check import (
    main as stability_change_report_main,
)
from app.planning.validation.problem_validator_check import (
    main as formal_validator_main,
)
from app.simulation.baselines.reference_schedulers import (
    main as reference_scheduler_main,
)
from app.simulation.benchmarks import load_baseline, load_profile_set
from app.simulation.scenarios.p2_correctness import main as p2_correctness_main
from app.simulation.scenarios.disruption_replay_check import (
    main as disruption_replay_main,
)
from app.simulation.execution.simulator_check import (
    main as execution_simulator_main,
)
from scripts.p6_duration_contract_check import main as p6_duration_contract_main
from scripts.p6_duration_dataset_check import main as p6_duration_dataset_main
from scripts.p6_duration_evaluation_check import main as p6_duration_evaluation_main
from scripts.p6_duration_model_check import main as p6_duration_model_main
from scripts.p6_duration_runtime_check import main as p6_duration_runtime_main
from scripts.p8_machine_contract_check import main as p8_machine_contract_main

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
EXPECTED_FRONTEND_RUNTIME_DEPENDENCIES = {
    "@tanstack/react-query": "5.102.3",
    "antd": "6.6.1",
    "react": "19.2.8",
    "react-dom": "19.2.8",
    "react-router-dom": "7.18.2",
}
EXPECTED_FRONTEND_DEVELOPMENT_DEPENDENCIES = {
    "@playwright/test": "1.62.1",
    "@testing-library/dom": "10.4.1",
    "@testing-library/jest-dom": "7.0.1",
    "@testing-library/react": "16.3.2",
    "@testing-library/user-event": "14.6.6",
    "@types/node": "24.13.3",
    "@types/react": "19.2.18",
    "@types/react-dom": "19.2.5",
    "@vitejs/plugin-react": "6.1.0",
    "axe-core": "4.13.0",
    "eslint": "10.9.1",
    "eslint-plugin-react-hooks": "7.1.1",
    "eslint-plugin-react-refresh": "0.5.4",
    "globals": "17.11.0",
    "jsdom": "30.0.1",
    "typescript": "6.0.3",
    "typescript-eslint": "8.68.0",
    "vite": "8.2.2",
    "vitest": "4.1.11",
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


def test_p3_frontend_dependencies_and_ci_are_exact_and_bounded() -> None:
    package = cast(
        dict[str, Any],
        json.loads((ROOT / "frontend" / "package.json").read_text(encoding="utf-8")),
    )
    lock = cast(
        dict[str, Any],
        json.loads(
            (ROOT / "frontend" / "package-lock.json").read_text(encoding="utf-8")
        ),
    )
    assert package["engines"] == {"node": "24.19.0", "npm": "11.17.0"}
    assert package["packageManager"] == "npm@11.17.0"
    assert package["dependencies"] == EXPECTED_FRONTEND_RUNTIME_DEPENDENCIES
    assert package["devDependencies"] == EXPECTED_FRONTEND_DEVELOPMENT_DEPENDENCIES
    assert lock["lockfileVersion"] == 3
    lock_root = cast(dict[str, Any], lock["packages"])[""]
    assert lock_root["engines"] == package["engines"]
    assert lock_root["dependencies"] == package["dependencies"]
    assert lock_root["devDependencies"] == package["devDependencies"]
    typescript_eslint = cast(dict[str, Any], lock["packages"])[
        "node_modules/typescript-eslint"
    ]
    assert typescript_eslint["version"] == "8.68.0"
    assert typescript_eslint["peerDependencies"]["eslint"] == (
        "^8.57.0 || ^9.0.0 || ^10.0.0"
    )
    assert typescript_eslint["peerDependencies"]["typescript"] == (">=4.8.4 <6.1.0")
    assert "registry.npmmirror.com" not in json.dumps(lock)

    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    normalized = " ".join(workflow.split())
    for fragment in (
        'node-version: "24.19.0"',
        'test "$(node --version)" = "v24.19.0"',
        'test "$(npm --version)" = "11.17.0"',
        "npm --prefix frontend ci",
        "npm --prefix frontend run audit:sca -- --report ../build/validation/ci-p3-frontend-sca.json",
        "npm --prefix frontend run licenses:check -- --report ../build/validation/ci-p3-frontend-licenses.json",
        "npm --prefix frontend run lint",
        "npm --prefix frontend run typecheck",
        "working-directory: frontend",
        "npm exec -- vitest --exclude=e2e/** --run",
        "npm --prefix frontend exec -- playwright install --with-deps chromium",
        "npm --prefix frontend run test:e2e",
        "npm --prefix frontend run build",
        "npm --prefix frontend run evidence -- --report ../build/validation/ci-p3-frontend.json",
    ):
        assert fragment in normalized
    assert "build/playwright/**" in workflow
    assert "continue-on-error" not in workflow


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
        "app.simulation.scenarios.p2_correctness",
        "build/validation/ci-p2-correctness.json",
        "app.simulation.baselines.reference_schedulers",
        "build/validation/ci-reference-schedulers.json",
        "app.exporters.contract_check",
        "build/validation/ci-p2-output-contracts.json",
        "app.domain.workspace_contract_check",
        "build/validation/ci-p3-workspace-contracts.json",
        "app.domain.execution_contract_check",
        "build/validation/ci-p4-machine-contracts.json",
        "app.infrastructure.workspace_persistence_check",
        "build/validation/ci-p3-persistence.json",
        "app.infrastructure.replan_persistence_check",
        "build/validation/ci-p4-replan-persistence.json",
        "app.application.execution_fact_projection_check",
        "build/validation/ci-p4-execution-fact-projection.json",
        "app.planning.problem.freeze_window_check",
        "build/validation/ci-p4-freeze-window.json",
        "app.planning.reporting.stability_change_report_check",
        "build/validation/ci-p4-stability-change-report.json",
        "app.planning.backends.cp_sat.replan_solver_check",
        "build/validation/ci-p4-replan-solver.json",
        "app.application.replan_application_check",
        "build/validation/ci-p4-replan-application.json",
        "app.application.schedule_version_lifecycle_check",
        "build/validation/ci-p3-schedule-version-lifecycle.json",
        "app.application.workspace_read_model_check",
        "build/validation/ci-p3-workspace-read-models.json",
        "app.application.schedule_command_check",
        "build/validation/ci-p3-schedule-commands.json",
        "app.application.approval_decision_check",
        "build/validation/ci-p3-approval-decisions.json",
        "app.application.publication_check",
        "build/validation/ci-p3-publication.json",
        "app.infrastructure.contract_check",
        "docker compose --env-file .env.example config --quiet",
        "PLANTNEXUS_CI_CHANGE_BASE:",
        "github.event.pull_request.base.sha || github.event.before",
        "--discover-task-from",
        "build/traceability/ci-current-task-report.json",
        "uv build",
        "PLANTNEXUS_BENCHMARK_PROFILE: xs",
        "--report build/benchmarks/ci-xs.json",
        "name: P2 vertical slice Gate evidence",
        "app.application.p2_gate_report",
        "build/validation/ci-p2-vertical-slice-gate.json",
        "build/benchmarks/*.json",
    )
    for fragment in required_fragments:
        assert fragment in workflow
    assert "scripts/run_benchmark.py" in workflow
    assert "name: P2 XS BenchmarkRunner evidence" in workflow
    assert "name: P2 vertical slice Gate evidence" in workflow
    assert "name: P3 workspace schema contract evidence" in workflow
    assert "name: P4 dynamic replanning machine contract evidence" in workflow
    assert "name: P3 workspace persistence evidence" in workflow
    assert "name: P4 replan event persistence evidence" in workflow
    assert "name: P4 ExecutionEvent fact projection evidence" in workflow
    assert "name: P4 freeze window and effective lock evidence" in workflow
    assert "name: P4 OBJ-002 stability and ChangeReport evidence" in workflow
    assert "name: P3 reviewable ScheduleVersion lifecycle evidence" in workflow
    assert "name: P3 workspace read model and comparison evidence" in workflow
    assert "name: P3 schedule edit and lock command evidence" in workflow
    assert "name: P3 approval rejection and audit evidence" in workflow
    assert "name: P3 publication supersession and idempotency evidence" in workflow
    assert "Benchmark hook (deferred until runner exists)" not in workflow
    assert "Benchmark runner remains deferred" not in workflow
    for action in (
        "actions/checkout@v7",
        "actions/setup-python@v7",
        "actions/setup-node@v7",
        "actions/upload-artifact@v7",
        "astral-sh/setup-uv@v10.0.1",
    ):
        assert action in workflow
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


def test_ci_profile_routing_is_mutually_exclusive_and_fail_closed() -> None:
    workflow_path = ROOT / ".github" / "workflows" / "ci.yml"
    workflow_text = workflow_path.read_text(encoding="utf-8")
    workflow = cast(dict[str, Any], yaml.safe_load(workflow_text))
    jobs = cast(dict[str, Any], workflow["jobs"])

    assert set(jobs) == {
        "classify",
        "docs_validation",
        "full_preflight",
        "full_backend",
        "full_validation",
        "validate",
    }
    classify = cast(dict[str, Any], jobs["classify"])
    docs = cast(dict[str, Any], jobs["docs_validation"])
    preflight = cast(dict[str, Any], jobs["full_preflight"])
    backend = cast(dict[str, Any], jobs["full_backend"])
    full = cast(dict[str, Any], jobs["full_validation"])
    final = cast(dict[str, Any], jobs["validate"])

    assert classify["outputs"] == {"profile": "${{ steps.profile.outputs.profile }}"}
    assert docs["needs"] == "classify"
    assert docs["if"] == "${{ needs.classify.outputs.profile == 'DOCS_ONLY' }}"
    assert preflight["needs"] == "classify"
    assert preflight["if"] == "${{ needs.classify.outputs.profile == 'FULL' }}"
    assert backend["needs"] == ["classify", "full_preflight"]
    assert backend["if"] == "${{ needs.classify.outputs.profile == 'FULL' }}"
    assert full["needs"] == ["classify", "full_preflight"]
    assert full["if"] == "${{ needs.classify.outputs.profile == 'FULL' }}"
    assert backend["env"] == full["env"]
    assert final["needs"] == [
        "classify",
        "docs_validation",
        "full_preflight",
        "full_backend",
        "full_validation",
    ]
    assert final["if"] == "${{ always() }}"

    classify_text = json.dumps(classify)
    docs_text = json.dumps(docs)
    preflight_text = json.dumps(preflight)
    backend_text = json.dumps(backend)
    full_text = json.dumps(full)
    final_run = cast(dict[str, Any], final["steps"][0])["run"]
    assert "scripts/ci_validation_profile.py classify" in classify_text
    assert "--github-output" in classify_text
    assert "scripts/ci_validation_profile.py validate-docs" in docs_text
    assert "setup-uv" not in docs_text
    assert "setup-node" not in docs_text
    assert "uv run" not in docs_text
    assert "npm " not in docs_text
    assert "scripts/ci_preflight.py" in preflight_text
    assert "setup-uv" not in preflight_text
    assert "setup-node" not in preflight_text
    assert "plantnexus-ci-preflight-${{ github.run_id }}" in preflight_text
    assert "uv sync --locked" in backend_text
    assert "uv run ruff check ." in backend_text
    assert "uv run pyright backend/app backend/tests" in backend_text
    assert "backend/tests/security" in backend_text
    assert "ci-backend-tests.xml" in backend_text
    assert "mkdir -p build/validation" in backend_text
    assert "plantnexus-ci-backend-${{ github.run_id }}" in backend_text
    assert "uv sync --locked" in full_text
    assert "backend/tests/security" not in full_text
    assert "TASK-P4-13 Dynamic replanning frontend machine evidence" in full_text
    assert "p4-replanning-replay.XXXXXX" in full_text
    assert "git worktree add --detach" in full_text
    assert "p5_portfolio_gate_report.py" in full_text
    assert "p5_exit_gate_audit.py" in full_text
    assert "test_p5_portfolio_gate_rejections.py" in full_text
    assert "test_p5_exit_gate_rejections.py" in full_text
    assert "test_p6_duration_contracts.py" in full_text
    assert "test_p5_portfolio_gate.py" in full_text
    assert "test_p5_exit_gate.py" in full_text
    assert f"--source {P5_EXIT_DIFF_BASE}" in full_text
    assert "-- backend/tests/integration/test_ci_contract.py" in full_text
    assert "backend/app/__init__.py" in full_text
    assert "schemas/data_dictionary.yaml" in full_text
    assert "duration-prediction.schema.json" in full_text
    assert "duration-prediction.v1.unknown-fallback.invalid.json" in full_text
    assert "ci-p4-replanning-api.json" in full_text
    assert "build/playwright/results.json" in full_text
    assert "P3 vertical slice Gate evidence" in full_text
    assert "P4 vertical slice Gate evidence" in full_text
    assert "app.application.p5_portfolio_gate_report" in full_text
    assert "app.application.p5_exit_gate_audit" in full_text
    assert "Build package" in full_text
    assert len(preflight["steps"]) == 4
    assert len(backend["steps"]) == 8
    assert len(full["steps"]) == 71

    assert 'test "${PLANTNEXUS_CLASSIFY_RESULT}" = "success"' in final_run
    assert 'test "${PLANTNEXUS_PREFLIGHT_RESULT}" = "success"' in final_run
    assert 'test "${PLANTNEXUS_BACKEND_RESULT}" = "success"' in final_run
    assert 'test "${PLANTNEXUS_FULL_RESULT}" = "success"' in final_run
    assert 'test "${PLANTNEXUS_DOCS_RESULT}" = "success"' in final_run
    assert final_run.count('= "skipped"') == 4
    assert "Unknown or missing CI validation profile" in final_run
    assert "continue-on-error" not in workflow_text


def test_ci_p3_workspace_schema_contract_is_required_and_machine_checkable(
    tmp_path: Path,
) -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    normalized = " ".join(workflow.split())
    assert (
        "name: P3 workspace schema contract evidence run: >- uv run python -m "
        "app.domain.workspace_contract_check --root . --report "
        "build/validation/ci-p3-workspace-contracts.json"
    ) in normalized
    assert "continue-on-error" not in workflow

    report_path = tmp_path / "p3-workspace-contracts.json"
    assert (
        workspace_contract_main(["--root", str(ROOT), "--report", str(report_path)])
        == 0
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["report_version"] == "p3-workspace-contract-report.v1"
    assert report["status"] == "PASS"
    assert report["task_id"] == "TASK-P3-02"
    assert report["schema_set_version"] == "2.6.0"
    assert report["check_count"] == 8
    assert report["counts"] == {
        "new_schemas": 7,
        "new_samples": 7,
        "frozen_p2_artifacts": 34,
        "negative_schema_rejections": 24,
        "negative_fingerprint_rejections": 6,
    }


def test_ci_p4_machine_contract_is_required_and_machine_checkable(
    tmp_path: Path,
) -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    normalized = " ".join(workflow.split())
    assert (
        "name: P4 dynamic replanning machine contract evidence run: >- "
        "uv run python -m app.domain.execution_contract_check --root . --report "
        "build/validation/ci-p4-machine-contracts.json"
    ) in normalized
    assert "continue-on-error" not in workflow

    report_path = tmp_path / "p4-machine-contracts.json"
    assert (
        execution_contract_main(["--root", str(ROOT), "--report", str(report_path)])
        == 0
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["report_version"] == "p4-machine-contract-report.v1"
    assert report["status"] == "PASS"
    assert report["task_id"] == "TASK-P4-02"
    assert report["diff_base"] == "4026597ab1015b5ea3a89d241f0d12b5b481dee3"
    assert report["schema_set_version"] == "2.8.0"
    assert report["check_count"] == 8
    assert report["issues"] == []


def test_ci_p6_duration_contract_is_required_and_machine_checkable(
    tmp_path: Path,
) -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    normalized = " ".join(workflow.split())
    assert (
        "name: P6 duration prediction machine contract evidence run: >- "
        "uv run python scripts/p6_duration_contract_check.py --root . --report "
        "build/validation/ci-p6-duration-contracts.json"
    ) in normalized
    assert "continue-on-error" not in workflow

    report_path = tmp_path / "p6-duration-contracts.json"
    assert (
        p6_duration_contract_main(
            ["--root", str(ROOT), "--report", str(report_path)]
        )
        == 0
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["report_version"] == "p6-duration-contract-report.v1"
    assert report["status"] == "PASS"
    assert report["task_id"] == "TASK-P6-02"
    assert report["diff_base"] == "e74099ca24ed59140f6490c84025b7299b5f201d"
    assert report["schema_set_version"] == "2.9.0"
    assert report["check_count"] == 10
    assert report["counts"] == {
        "new_schemas": 4,
        "positive_samples": 5,
        "negative_samples": 5,
        "frozen_historical_artifacts": 70,
        "schema_rejections": 20,
        "semantic_rejections": 7,
        "tamper_rejections": 5,
    }
    assert report["issues"] == []


def test_ci_p8_machine_contract_is_required_and_machine_checkable(
    tmp_path: Path,
) -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    normalized = " ".join(workflow.split())
    assert (
        "name: P8 canonical ingress and PlanningRun machine contract evidence "
        "run: >- uv run python scripts/p8_machine_contract_check.py --root . "
        "--report build/validation/ci-p8-machine-contracts.json"
    ) in normalized
    assert "continue-on-error" not in workflow
    for relative_path in (
        "backend/tests/contract/test_p8_machine_contracts.py",
        "schemas/json/canonical-ingress-request.schema.json",
        "schemas/json/canonical-ingress-result.schema.json",
        "schemas/json/planning-run.schema.json",
        "schemas/rules/headless-error-code-registry.v1.yaml",
        "schemas/samples/canonical-ingress-request.v1.synthetic.json",
        "schemas/samples/canonical-ingress-result.v1.accepted.synthetic.json",
        "schemas/samples/canonical-ingress-result.v1.rejected.synthetic.json",
        "schemas/samples/canonical-ingress.v1.invalid-authority.synthetic.json",
        "schemas/samples/canonical-ingress.v1.invalid-fingerprint.synthetic.json",
        "schemas/samples/canonical-ingress.v1.invalid-idempotency.synthetic.json",
        "schemas/samples/canonical-ingress.v1.invalid-plane.synthetic.json",
        "schemas/samples/canonical-ingress.v1.invalid-reference.synthetic.json",
        "schemas/samples/canonical-ingress.v1.invalid-scope.synthetic.json",
        "schemas/samples/canonical-ingress.v1.invalid-type.synthetic.json",
        "schemas/samples/canonical-ingress.v1.invalid-unknown-field.synthetic.json",
        "schemas/samples/canonical-ingress.v1.invalid-version.synthetic.json",
        "schemas/samples/planning-run.v1.completed.synthetic.json",
        "schemas/samples/planning-run.v1.created.synthetic.json",
        "schemas/samples/planning-run.v1.invalid-transition.synthetic.json",
    ):
        assert workflow.count(f'"${{replay_root}}/{relative_path}"') == 1

    report_path = tmp_path / "p8-machine-contracts.json"
    assert (
        p8_machine_contract_main(
            ["--root", str(ROOT), "--report", str(report_path)]
        )
        == 0
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["report_version"] == "p8-machine-contract-report.v1"
    assert report["status"] == "PASS"
    assert report["task_id"] == "TASK-P8-02"
    assert report["diff_base"] == "43ff13429b2bb79854f976c0a1f5a72b1b069607"
    assert report["schema_set_version"] == "2.10.0"
    assert report["check_count"] == 6
    assert report["counts"] == {
        "immutable_historical_artifacts": 97,
        "negative_samples": 10,
        "new_rule_registries": 1,
        "new_schemas": 3,
        "positive_samples": 5,
    }
    assert report["issues"] == []


def test_ci_p6_duration_dataset_is_required_and_machine_checkable(
    tmp_path: Path,
) -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    normalized = " ".join(workflow.split())
    assert (
        "name: P6 feature label dataset evidence run: >- "
        "uv run python scripts/p6_duration_dataset_check.py --root . --report "
        "build/validation/ci-p6-duration-dataset.json"
    ) in normalized
    assert "continue-on-error" not in workflow
    assert '"${replay_root}/backend/app/duration_prediction/__init__.py"' in workflow
    assert '"${replay_root}/backend/app/duration_prediction/dataset.py"' in workflow
    assert '"${replay_root}/backend/tests/contract/test_p6_duration_dataset.py"' in workflow

    report_path = tmp_path / "p6-duration-dataset.json"
    assert (
        p6_duration_dataset_main(
            ["--root", str(ROOT), "--report", str(report_path)]
        )
        == 0
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["report_version"] == "p6-duration-dataset-report.v1"
    assert report["status"] == "PASS"
    assert report["task_id"] == "TASK-P6-03"
    assert report["diff_base"] == "4360746f2712012a0aa4f52a40c189837a2097b3"
    assert report["schema_set_version"] == "2.9.0"
    assert report["check_count"] == 10
    assert report["counts"] == {
        "source_records": 10,
        "eligible_rows": 8,
        "excluded_records": 2,
        "train_rows": 4,
        "validation_rows": 2,
        "test_rows": 2,
        "feature_records": 8,
        "features": 32,
        "mutation_rejections": 12,
    }
    assert report["artifacts"]["source"]["included_in_provider_artifact"] is False
    assert report["artifacts"]["expected_bundle"]["included_in_provider_artifact"] is False
    assert report["boundaries"]["production_binding"] is False
    assert report["issues"] == []


def test_ci_p6_duration_model_is_required_and_machine_checkable(
    tmp_path: Path,
) -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    normalized = " ".join(workflow.split())
    assert (
        "name: P6 versioned baseline model and replay evidence run: >- "
        "uv run python scripts/p6_duration_model_check.py --root . --report "
        "build/validation/ci-p6-duration-model.json --model-artifact "
        "build/validation/ci-p6-duration-baseline-model.json --manifest-artifact "
        "build/validation/ci-p6-duration-model-manifest.json --replay-artifact "
        "build/validation/ci-p6-duration-model-replay.json"
    ) in normalized
    assert "continue-on-error" not in workflow
    assert '"${replay_root}/backend/app/duration_prediction/model.py"' in workflow
    assert '"${replay_root}/backend/tests/contract/test_p6_duration_model.py"' in workflow

    report_path = tmp_path / "p6-duration-model.json"
    model_path = tmp_path / "p6-duration-baseline-model.json"
    manifest_path = tmp_path / "p6-duration-model-manifest.json"
    replay_path = tmp_path / "p6-duration-model-replay.json"
    assert (
        p6_duration_model_main(
            [
                "--root",
                str(ROOT),
                "--report",
                str(report_path),
                "--model-artifact",
                str(model_path),
                "--manifest-artifact",
                str(manifest_path),
                "--replay-artifact",
                str(replay_path),
            ]
        )
        == 0
    )

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["report_version"] == "p6-duration-model-report.v1"
    assert report["status"] == "PASS"
    assert report["task_id"] == "TASK-P6-04"
    assert report["diff_base"] == "1d184d082544454436a5558bc39a6a0a38f0fb1b"
    assert report["schema_set_version"] == "2.9.0"
    assert report["check_count"] == 10
    assert report["counts"] == {
        "atomic_rejections": 2,
        "dataset_rows": 8,
        "model_parameters": 3,
        "mutation_rejections": 14,
        "operation_families": 2,
        "replayed_estimates": 8,
        "test_rows_used_for_training": 0,
        "training_rows": 4,
        "validation_rows_used_for_training": 0,
    }
    assert report["artifacts"]["dataset_source"]["included_in_provider_artifact"] is False
    assert report["artifacts"]["model_bundle"]["included_in_provider_artifact"] is False
    assert report["artifacts"]["model_artifact"]["safe_for_provider"] is True
    assert report["boundaries"]["production_authorized"] is False
    assert report["boundaries"]["runtime_or_planning_authority"] == "NONE"
    assert report["issues"] == []

    model = json.loads(model_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    replay = json.loads(replay_path.read_text(encoding="utf-8"))
    assert model["duration_baseline_artifact_version"] == "duration-baseline-artifact.v1"
    assert model["model_version"] == "1.0.0"
    assert model["governance_boundary"]["production_authorized"] is False
    assert manifest["duration_model_manifest_version"] == "duration-model-manifest.v1"
    assert manifest["model_artifact"]["artifact_digest"] == replay["model_artifact_digest"]
    assert replay["document_version"] == "duration-training-replay.v1"
    assert replay["boundaries"]["labels_in_replay_artifact"] is False
    assert all("label" not in entry for entry in replay["estimates"])


def test_ci_p6_duration_runtime_is_required_and_machine_checkable(
    tmp_path: Path,
) -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )
    normalized = " ".join(workflow.split())
    assert (
        "uv run python scripts/p6_duration_evaluation_check.py --root . --report "
        "build/validation/ci-p6-duration-evaluation.json && uv run python "
        "scripts/p6_duration_runtime_check.py --root . --offline-gate-report "
        "build/validation/ci-p6-duration-evaluation.json --report "
        "build/validation/ci-p6-duration-runtime.json"
    ) in normalized
    assert workflow.count("scripts/p6_duration_runtime_check.py") == 1
    assert "continue-on-error" not in workflow
    for relative_path in (
        "backend/app/duration_prediction/runtime.py",
        "backend/tests/p6_duration_runtime_support.py",
        "backend/tests/contract/test_p6_duration_runtime.py",
        "backend/tests/property/test_p6_duration_runtime_properties.py",
        "backend/tests/contract/test_p6_duration_runtime_security.py",
        "backend/tests/performance/test_p6_duration_runtime_performance.py",
        "backend/tests/validation/test_p6_duration_runtime_mutations.py",
    ):
        assert f'"${{replay_root}}/{relative_path}"' in workflow

    offline_report = tmp_path / "p6-duration-evaluation.json"
    runtime_report = tmp_path / "p6-duration-runtime.json"
    monitoring_report = tmp_path / "p6-duration-monitoring.json"
    assert (
        p6_duration_evaluation_main(
            ["--root", str(ROOT), "--report", str(offline_report)]
        )
        == 0
    )
    assert (
        p6_duration_runtime_main(
            [
                "--root",
                str(ROOT),
                "--offline-gate-report",
                str(offline_report),
                "--report",
                str(runtime_report),
                "--monitoring-report",
                str(monitoring_report),
            ]
        )
        == 0
    )
    report = json.loads(runtime_report.read_text(encoding="utf-8"))
    monitor = json.loads(monitoring_report.read_text(encoding="utf-8"))
    assert report["schema_version"] == "p6-duration-runtime-check-report.v1"
    assert report["task_id"] == "TASK-P6-06"
    assert report["diff_base"] == "9921e57034defc26c0a08b7b0c27da3398a0fc7e"
    assert report["result"] == "PASS"
    assert report["counts"] == {
        "candidate_carriers": 8,
        "feature_records": 8,
        "label_semantic_reads": 0,
        "registered_fallback_reasons": 19,
        "same_input_replays": 8,
        "schema_rejections": 0,
        "standard_authority_mutations": 0,
    }
    assert report["boundaries"] == {
        "business_state_write": "NONE",
        "cache": "NONE",
        "data_plane": "SIMULATION",
        "environment": "TEST",
        "network_external_service": "NONE",
        "planning_authority": "ADVISORY_DURATION_ONLY_NO_CONSUMER",
        "production_authorized": False,
        "production_sla_claimed": False,
        "provider": "IN_PROCESS_EXPLICIT_INVOCATION_ONLY",
    }
    assert monitor["schema_version"] == "p6-duration-monitoring-check-report.v1"
    assert monitor["task_id"] == "TASK-P6-08"
    assert monitor["diff_base"] == "e5d63fcf54c841ed93ef7c62084bcdeeda63abd4"
    assert monitor["result"] == "PASS"
    assert len(monitor["checks"]) == 12
    assert monitor["blocking_gaps"] == []
    assert monitor["issues"] == []
    assert monitor["safe_artifact_boundary"] == {
        "feature_records_included": False,
        "labels_included": False,
        "operation_or_resource_ids_included": False,
        "raw_predictions_included": False,
        "source_record_ids_included": False,
    }
    runtime_source = (ROOT / "scripts" / "p6_duration_runtime_check.py").read_text(
        encoding="utf-8"
    )
    assert runtime_source.count("monitoring_check_main") == 2
    assert "scripts/p6_duration_monitoring_check.py" not in workflow
    assert report["issues"] == []


def test_ci_p6_planning_ingress_is_isolated_from_frozen_p4_replay() -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )
    for relative_path in (
        "backend/app/duration_prediction/planning_ingress.py",
        "backend/tests/p6_planning_integration_support.py",
        "backend/tests/contract/test_p6_planning_ingress_contract.py",
        "backend/tests/integration/test_p6_planning_ingress_integration.py",
        "backend/tests/property/test_p6_planning_integration_properties.py",
        "backend/tests/validation/test_p6_planning_integration_mutations.py",
    ):
        assert workflow.count(f'"${{replay_root}}/{relative_path}"') == 1


def test_ci_p3_persistence_is_required_and_machine_checkable(tmp_path: Path) -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    normalized = " ".join(workflow.split())
    assert (
        "name: P3 workspace persistence evidence run: >- uv run python -m "
        "app.infrastructure.workspace_persistence_check --root . --report "
        "build/validation/ci-p3-persistence.json"
    ) in normalized
    assert "continue-on-error" not in workflow

    report_path = tmp_path / "p3-persistence.json"
    assert (
        workspace_persistence_main(["--root", str(ROOT), "--report", str(report_path)])
        == 0
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["report_version"] == "p3-persistence-report.v1"
    assert report["status"] == "PASS"
    assert report["task_id"] == "TASK-P3-03"
    assert report["migration_revision"] == ("0004_schedule_versions_audit_export_jobs")
    assert report["check_count"] == 8
    assert report["counts"] == {
        "tables": 5,
        "repositories": 4,
        "machine_checks": 8,
        "database_mutation_rejections": 4,
        "plane_mismatch_rejections": 2,
    }


def test_ci_p4_replan_persistence_is_required_and_machine_checkable(
    tmp_path: Path,
) -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    normalized = " ".join(workflow.split())
    assert (
        "name: P4 replan event persistence evidence run: >- uv run python -m "
        "app.infrastructure.replan_persistence_check --root . --report "
        "build/validation/ci-p4-replan-persistence.json"
    ) in normalized
    assert "continue-on-error" not in workflow

    report_path = tmp_path / "p4-replan-persistence.json"
    assert (
        replan_persistence_main(["--root", str(ROOT), "--report", str(report_path)])
        == 0
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["report_version"] == "p4-replan-persistence-report.v1"
    assert report["status"] == "PASS"
    assert report["task_id"] == "TASK-P4-03"
    assert report["diff_base"] == "7b9bfc3069de5d3738e5cc5827d27d197ed3d226"
    assert report["migration_revision"] == "0005_replan_event_persistence"
    assert report["check_count"] == 9
    assert report["issues"] == []
    assert report["counts"] == {
        "tables": 7,
        "repositories": 5,
        "machine_checks": 9,
        "database_mutation_rejections": 8,
        "production_write_rejections": 1,
        "p3_rows_retained": 1,
    }


def test_ci_p4_execution_fact_projection_is_required_and_machine_checkable(
    tmp_path: Path,
) -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    normalized = " ".join(workflow.split())
    assert (
        "name: P4 ExecutionEvent fact projection evidence run: >- "
        "uv run python -m app.application.execution_fact_projection_check "
        "--root . --report build/validation/ci-p4-execution-fact-projection.json"
    ) in normalized
    assert "continue-on-error" not in workflow

    report_path = tmp_path / "p4-execution-fact-projection.json"
    assert (
        execution_fact_projection_main(
            ["--root", str(ROOT), "--report", str(report_path)]
        )
        == 0
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["report_version"] == "p4-execution-fact-projection-report.v1"
    assert report["status"] == "PASS"
    assert report["task_id"] == "TASK-P4-04"
    assert report["diff_base"] == "3563bb236ce7b2c01794485110d4945a6e265105"
    assert report["check_count"] == 8
    assert report["issues"] == []
    assert report["counts"] == {
        "event_types": 11,
        "positive_event_vectors": 11,
        "negative_vectors": 4,
        "standard_urgent_imports": 1,
        "durable_event_rows": 3,
        "committed_projection_snapshots": 2,
        "atomic_rollback_cases": 1,
        "machine_checks": 8,
    }


def test_ci_p4_freeze_window_is_required_and_machine_checkable(
    tmp_path: Path,
) -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    normalized = " ".join(workflow.split())
    assert (
        "name: P4 freeze window and effective lock evidence run: >- "
        "uv run python -m app.planning.problem.freeze_window_check "
        "--root . --report build/validation/ci-p4-freeze-window.json"
    ) in normalized
    assert "continue-on-error" not in workflow

    report_path = tmp_path / "p4-freeze-window.json"
    assert freeze_window_main(["--root", str(ROOT), "--report", str(report_path)]) == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["report_version"] == "p4-freeze-window-report.v1"
    assert report["status"] == "PASS"
    assert report["task_id"] == "TASK-P4-05"
    assert report["diff_base"] == "e7b96e28913e7eb5be63ae4265c09f8281456b1c"
    assert report["check_count"] == 7
    assert report["issues"] == []
    assert report["counts"] == {
        "simulation_policies": 1,
        "event_derived_snapshots": 2,
        "positive_projection_vectors": 4,
        "negative_projection_vectors": 4,
        "independent_mutation_vectors": 1,
        "machine_checks": 7,
    }
    assert report["boundaries"] == {
        "data_plane": "SIMULATION_ONLY",
        "freeze_policy": "SIM-P4-FREEZE-001_VERSIONED_900_SECONDS",
        "interval_semantics": "HALF_OPEN_START_INCLUSIVE_END_EXCLUSIVE",
        "production_freeze_default": "OPEN_005_NOT_FORMED",
        "problem_v2_bytes": "UNCHANGED_REFERENCED_CARRIER",
        "solver_obj_002_change_report": "NOT_IMPLEMENTED_BY_TASK",
        "schedule_version_or_state_transition": "NONE",
        "formal_validator_c001_c011": "UNCHANGED_INDEPENDENT_PRECHECK",
        "p4_06_plus": "NOT_STARTED",
        "p5_plus": "NOT_STARTED",
        "production_external_authority_capacity_sla": "NOT_ESTABLISHED",
    }


def test_ci_p4_stability_change_report_is_required_and_machine_checkable(
    tmp_path: Path,
) -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    normalized = " ".join(workflow.split())
    assert (
        "name: P4 OBJ-002 stability and ChangeReport evidence run: >- "
        "uv run python -m app.planning.reporting.stability_change_report_check "
        "--root . --report build/validation/ci-p4-stability-change-report.json"
    ) in normalized
    assert "continue-on-error" not in workflow

    report_path = tmp_path / "p4-stability-change-report.json"
    assert (
        stability_change_report_main(
            ["--root", str(ROOT), "--report", str(report_path)]
        )
        == 0
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["report_version"] == "p4-stability-change-report.v1"
    assert report["status"] == "PASS"
    assert report["task_id"] == "TASK-P4-06"
    assert report["diff_base"] == "d9d9f2fa2dbefe4c9942aaa8a943a93fdc7efd43"
    assert report["impact_rule_count"] == 6
    assert report["impact_rules"] == [
        "IMPACT-DOCS",
        "IMPACT-DOMAIN",
        "IMPACT-INFRA",
        "IMPACT-REPORTING",
        "IMPACT-TESTS",
        "IMPACT-VALIDATOR",
    ]
    assert report["check_count"] == 8
    assert report["issues"] == []
    assert report["counts"] == {
        "operation_universe": 4,
        "positive_vectors": 1,
        "mutation_vectors": 5,
        "invalid_input_vectors": 4,
        "machine_checks": 8,
    }
    assert report["boundaries"] == {
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


def test_ci_p4_replan_solver_is_required_and_machine_checkable(
    tmp_path: Path,
) -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    normalized = " ".join(workflow.split())
    assert (
        "name: P4 lexicographic replan solver and validator evidence run: >- "
        "uv run python -m app.planning.backends.cp_sat.replan_solver_check "
        "--root . --report build/validation/ci-p4-replan-solver.json"
    ) in normalized
    assert "continue-on-error" not in workflow

    report_path = tmp_path / "p4-replan-solver.json"
    assert replan_solver_main(["--root", str(ROOT), "--report", str(report_path)]) == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["report_version"] == "p4-replan-solver-report.v1"
    assert report["status"] == "PASS"
    assert report["task_id"] == "TASK-P4-07"
    assert report["diff_base"] == "e212ab7957d6bc5887048ee54809c8194d6e1eaf"
    assert report["impact_rule_count"] == 7
    assert report["impact_rules"] == [
        "IMPACT-BACKEND",
        "IMPACT-DOCS",
        "IMPACT-INFRA",
        "IMPACT-STATE",
        "IMPACT-STRATEGY",
        "IMPACT-TESTS",
        "IMPACT-VALIDATOR",
    ]
    assert report["check_count"] == 8
    assert report["issues"] == []
    assert report["counts"] == {
        "objective_stages": 3,
        "solver_rounds": 6,
        "fresh_validations": 6,
        "deterministic_replays": 2,
        "machine_checks": 8,
    }
    assert report["boundaries"] == {
        "data_plane": "SIMULATION_ONLY",
        "solver_scope": "GLOBAL_C001_C011_NO_DECOMPOSITION",
        "base_schedule": "HINT_ONLY_EXCEPT_EFFECTIVE_HARD_PROTECTIONS",
        "change_report": "ARITHMETIC_AND_UNIVERSE_PRECHECK_ONLY",
        "schedule_version_or_state_transition": "NONE",
        "application_api_ui_simulator": "NOT_IMPLEMENTED_BY_TASK",
        "p4_08_plus": "NOT_STARTED",
        "p5_plus": "NOT_STARTED",
        "production_external_authority_capacity_sla": "NOT_ESTABLISHED",
    }


def test_ci_p4_replan_application_is_required_and_machine_checkable(
    tmp_path: Path,
) -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    normalized = " ".join(workflow.split())
    assert (
        "name: P4 replan application and ScheduleVersion lineage evidence run: >- "
        "uv run python -m app.application.replan_application_check --root . "
        "--report build/validation/ci-p4-replan-application.json"
    ) in normalized
    assert "continue-on-error" not in workflow

    report_path = tmp_path / "p4-replan-application.json"
    assert (
        replan_application_main(["--root", str(ROOT), "--report", str(report_path)])
        == 0
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["report_version"] == "p4-replan-application-report.v1"
    assert report["status"] == "PASS"
    assert report["task_id"] == "TASK-P4-08"
    assert report["diff_base"] == "77981f0564d91dfb57fee6e3792f4989bdb51d32"
    assert report["impact_rule_count"] == 6
    assert report["impact_rules"] == [
        "IMPACT-APPLICATION",
        "IMPACT-DOCS",
        "IMPACT-DOMAIN",
        "IMPACT-INFRA",
        "IMPACT-STATE",
        "IMPACT-TESTS",
    ]
    assert report["check_count"] == 8
    assert report["issues"] == []
    assert report["counts"] == {
        "execution_events": 4,
        "replan_requests": 1,
        "replan_attempts": 1,
        "replan_results": 1,
        "audit_records": 3,
        "schedule_versions_total": 2,
        "new_draft_schedule_versions": 1,
        "exact_replays": 1,
        "machine_checks": 8,
    }
    assert report["boundaries"] == {
        "data_plane": "SIMULATION_ONLY",
        "result_schedule_state": "DRAFT_ONLY",
        "base_published_schedule": "BYTE_EXACT_IMMUTABLE",
        "approval_publish_export": "NOT_INVOKED",
        "http_ui_execution_simulator": "NOT_IMPLEMENTED_BY_TASK",
        "p4_09_plus": "NOT_STARTED",
        "p5_plus": "NOT_STARTED",
        "production_external_authority_capacity_sla": "NOT_ESTABLISHED",
    }


def test_ci_p4_execution_simulator_is_required_and_machine_checkable(
    tmp_path: Path,
) -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    normalized = " ".join(workflow.split())
    assert (
        "name: P4 deterministic Execution Simulator core evidence run: >- "
        "uv run python -m app.simulation.execution.simulator_check --root . "
        "--report build/validation/ci-p4-execution-simulator.json"
    ) in normalized
    assert "continue-on-error" not in workflow

    report_path = tmp_path / "p4-execution-simulator.json"
    assert (
        execution_simulator_main(["--root", str(ROOT), "--report", str(report_path)])
        == 0
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["report_version"] == "p4-execution-simulator-report.v1"
    assert report["status"] == "PASS"
    assert report["task_id"] == "TASK-P4-09"
    assert report["diff_base"] == "e4874735166be93473ccaebaf1090980db957552"
    assert report["impact_rules"] == [
        "IMPACT-DOCS",
        "IMPACT-INFRA",
        "IMPACT-SIM-EXECUTION",
        "IMPACT-TESTS",
    ]
    assert report["check_count"] == 8
    assert report["issues"] == []
    assert report["counts"] == {
        "scheduled_events": 3,
        "same_offset_events": 2,
        "event_types": 3,
        "same_input_full_runs": 2,
        "checkpoint_batches": 2,
        "public_ingress_calls": 6,
        "frozen_boundary_files": 8,
        "machine_checks": 8,
    }
    assert report["boundaries"] == {
        "data_plane": "SIMULATION_ONLY",
        "time_source": "VERSIONED_VIRTUAL_CLOCK_ONLY",
        "event_output": "STANDARD_EXECUTION_EVENT_V1_ONLY",
        "common_ingress": ("P4_04_EXECUTION_FACT_PROJECTION_SERVICE_INGEST_EVENT"),
        "database_solver_replan_schedule_write": "NONE_IN_SIMULATOR_CORE",
        "fact_checkpoint": "EXPLICIT_CALLER_SUPPLIED_REFERENCE_ONLY",
        "five_disruption_continuous_replay": "P4_10_NOT_IMPLEMENTED",
        "business_state_transition": "NONE",
        "p5_plus": "EXPLICITLY_REJECTED",
        "production_external_authority_capacity_sla": "NOT_ESTABLISHED",
    }


def test_ci_p4_disruption_replay_is_required_and_machine_checkable(
    tmp_path: Path,
) -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    normalized = " ".join(workflow.split())
    assert (
        "name: P4 five-disruption continuous replay evidence run: >- "
        "uv run python -m app.simulation.scenarios.disruption_replay_check "
        "--root . --report build/validation/ci-p4-disruption-replay.json"
    ) in normalized
    assert "continue-on-error" not in workflow

    report_path = tmp_path / "p4-disruption-replay.json"
    assert (
        disruption_replay_main(["--root", str(ROOT), "--report", str(report_path)]) == 0
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["report_version"] == "p4-disruption-replay-report.v1"
    assert report["status"] == "PASS"
    assert report["task_id"] == "TASK-P4-10"
    assert report["diff_base"] == "8bbe0c643571e578ec637f135a2390c90de02512"
    assert report["impact_rules"] == [
        "IMPACT-DOCS",
        "IMPACT-FIXTURE",
        "IMPACT-INFRA",
        "IMPACT-SIM-SCENARIO",
        "IMPACT-TESTS",
    ]
    assert report["check_count"] == 8
    assert report["issues"] == []


def test_ci_p4_change_report_output_is_required_and_machine_checkable(
    tmp_path: Path,
) -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )
    normalized = " ".join(workflow.split())
    assert (
        "name: P4 ChangeReport read model and export evidence run: >- "
        "uv run python -m app.exporters.change_report_output_check --root . "
        "--report build/validation/ci-p4-change-report-output.json"
    ) in normalized
    assert "continue-on-error" not in workflow

    report_path = tmp_path / "p4-change-report-output.json"
    assert (
        change_report_output_main(
            ["--root", str(ROOT), "--report", str(report_path)]
        )
        == 0
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["report_version"] == "p4-change-report-output-report.v1"
    assert report["status"] == "PASS"
    assert report["task_id"] == "TASK-P4-11"
    assert report["diff_base"] == "45b12d9a67ce5ef1680a47fecdc68705355af226"
    assert report["impact_rules"] == [
        "IMPACT-APPLICATION",
        "IMPACT-DOCS",
        "IMPACT-DOMAIN",
        "IMPACT-EXPORT",
        "IMPACT-INFRA",
        "IMPACT-JOBS",
        "IMPACT-STATE",
        "IMPACT-TESTS",
    ]
    assert report["check_count"] == 8
    assert report["issues"] == []
    assert report["boundaries"]["publishable"] is False
    assert report["boundaries"]["p5_plus"] == "NOT_STARTED"


def test_ci_p3_schedule_version_lifecycle_is_required_and_machine_checkable(
    tmp_path: Path,
) -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    normalized = " ".join(workflow.split())
    assert (
        "name: P3 reviewable ScheduleVersion lifecycle evidence run: >- "
        "uv run python -m app.application.schedule_version_lifecycle_check "
        "--root . --report "
        "build/validation/ci-p3-schedule-version-lifecycle.json"
    ) in normalized
    assert "continue-on-error" not in workflow

    report_path = tmp_path / "p3-schedule-version-lifecycle.json"
    assert (
        schedule_version_lifecycle_main(
            ["--root", str(ROOT), "--report", str(report_path)]
        )
        == 0
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["report_version"] == ("p3-schedule-version-lifecycle-report.v1")
    assert report["status"] == "PASS"
    assert report["task_id"] == "TASK-P3-04"
    assert report["check_count"] == 8
    assert report["counts"]["reviewable_schedule_versions"] == 1
    assert report["counts"]["lifecycle_service_solver_invocations"] == 0
    assert report["boundaries"]["production_readiness"] == "NOT_CLAIMED"


def test_ci_p3_workspace_read_models_are_required_and_machine_checkable(
    tmp_path: Path,
) -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    normalized = " ".join(workflow.split())
    assert (
        "name: P3 workspace read model and comparison evidence run: >- "
        "uv run python -m app.application.workspace_read_model_check --root . "
        "--report build/validation/ci-p3-workspace-read-models.json"
    ) in normalized
    assert "continue-on-error" not in workflow

    report_path = tmp_path / "p3-workspace-read-models.json"
    assert (
        workspace_read_model_main(["--root", str(ROOT), "--report", str(report_path)])
        == 0
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["report_version"] == "p3-workspace-read-model-report.v1"
    assert report["status"] == "PASS"
    assert report["task_id"] == "TASK-P3-05"
    assert report["check_count"] == 8
    assert report["counts"]["workspace_views"] == 14
    assert report["counts"]["product_service_solver_invocations"] == 0
    assert report["boundaries"]["change_report_replan"] == "NOT_IMPLEMENTED"


def test_ci_p3_schedule_commands_are_required_and_machine_checkable(
    tmp_path: Path,
) -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    normalized = " ".join(workflow.split())
    assert (
        "name: P3 schedule edit and lock command evidence run: >- "
        "uv run python -m app.application.schedule_command_check --root . "
        "--report build/validation/ci-p3-schedule-commands.json"
    ) in normalized
    assert "continue-on-error" not in workflow

    report_path = tmp_path / "p3-schedule-commands.json"
    assert (
        schedule_command_main(["--root", str(ROOT), "--report", str(report_path)]) == 0
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["report_version"] == "p3-schedule-command-report.v1"
    assert report["status"] == "PASS"
    assert report["task_id"] == "TASK-P3-06"
    assert report["check_count"] == 8
    assert report["counts"]["command_types"] == 5
    assert report["counts"]["content_command_types"] == 4
    assert report["counts"]["review_submission_command_types"] == 1
    assert report["counts"]["fresh_validator_passes"] == 5
    assert report["counts"]["exact_replays"] == 2
    assert report["counts"]["product_service_solver_invocations"] == 0
    assert report["boundaries"]["source_content_update"] == ("FORBIDDEN_AND_ABSENT")
    assert report["boundaries"]["manual_draft_ready_transition"] == (
        "EXPLICIT_CAS_SAME_CONTENT"
    )
    assert report["boundaries"]["production_readiness"] == "NOT_CLAIMED"


def test_ci_p3_approval_decisions_are_required_and_machine_checkable(
    tmp_path: Path,
) -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    normalized = " ".join(workflow.split())
    assert (
        "name: P3 approval rejection and audit evidence run: >- "
        "uv run python -m app.application.approval_decision_check --root . "
        "--report build/validation/ci-p3-approval-decisions.json"
    ) in normalized
    assert "backend/tests/property" in normalized
    assert "backend/tests/security" in normalized
    assert "continue-on-error" not in workflow

    report_path = tmp_path / "p3-approval-decisions.json"
    assert (
        approval_decision_main(["--root", str(ROOT), "--report", str(report_path)]) == 0
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["report_version"] == "p3-approval-decision-report.v1"
    assert report["status"] == "PASS"
    assert report["task_id"] == "TASK-P3-07"
    assert report["check_count"] == 8
    assert report["counts"] == {
        "decision_types": 2,
        "successful_decisions": 3,
        "exact_replays": 2,
        "idempotency_conflicts": 1,
        "authorization_denials": 3,
        "denial_audits": 3,
        "rejected_requests_without_business_state": 4,
        "atomic_rollbacks": 1,
        "product_service_solver_invocations": 0,
    }
    assert report["boundaries"]["states_and_pairs"] == (
        "EXISTING_READY_TO_APPROVED_OR_REJECTED_ONLY"
    )
    assert report["boundaries"]["production_authority"] == ("DEFAULT_DENY_OPEN_010")
    assert report["boundaries"]["publish_export"] == "NOT_IMPLEMENTED"
    assert report["boundaries"]["production_readiness"] == "NOT_CLAIMED"


def test_ci_p3_publication_is_required_and_machine_checkable(
    tmp_path: Path,
) -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    normalized = " ".join(workflow.split())
    assert (
        "name: P3 publication supersession and idempotency evidence run: >- "
        "uv run python -m app.application.publication_check --root . "
        "--report build/validation/ci-p3-publication.json"
    ) in normalized
    assert "continue-on-error" not in workflow

    report_path = tmp_path / "p3-publication.json"
    assert publication_main(["--root", str(ROOT), "--report", str(report_path)]) == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["report_version"] == "p3-publication-report.v1"
    assert report["status"] == "PASS"
    assert report["task_id"] == "TASK-P3-08"
    assert report["check_count"] == 8
    assert report["counts"] == {
        "successful_publications": 3,
        "supersessions": 2,
        "exact_replays": 1,
        "idempotency_conflicts": 1,
        "authorization_denials": 2,
        "rejected_requests_without_business_state": 4,
        "atomic_rollbacks": 1,
        "concurrent_current_winners": 1,
        "product_service_solver_invocations": 0,
    }
    assert report["boundaries"]["publication_target"] == ("SIMULATION_INTERNAL_ONLY")
    assert report["boundaries"]["publish_export_separation"] == ("EXPORT_NOT_INVOKED")
    assert report["boundaries"]["production_authority"] == ("DEFAULT_DENY_OPEN_002_010")
    assert report["boundaries"]["production_readiness"] == "NOT_CLAIMED"


def test_ci_p3_export_job_is_required_and_machine_checkable(tmp_path: Path) -> None:
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    normalized = " ".join(workflow.split())
    assert (
        "name: P3 ExportJob and standard package evidence run: >- "
        "uv run python -m app.application.export_job_check --root . "
        "--report build/validation/ci-p3-export-jobs.json"
    ) in normalized
    assert "continue-on-error" not in workflow

    report_path = tmp_path / "p3-export-jobs.json"
    assert export_job_main(["--root", str(ROOT), "--report", str(report_path)]) == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["report_version"] == "p3-export-job-report.v1"
    assert report["status"] == "PASS"
    assert report["task_id"] == "TASK-P3-09"
    assert report["schema_set_version"] == "2.7.0"
    assert report["check_count"] == 8
    assert report["counts"] == {
        "new_schemas": 2,
        "new_samples": 2,
        "focused_tests": 18,
        "package_payloads": 12,
        "xlsx_sheets": 4,
        "export_states": 5,
        "export_allowed_pairs": 6,
        "provider_side_effects": 0,
    }
    assert report["boundaries"] == {
        "publish_service": "NOT_CALLED",
        "external_target": "ABSENT",
        "http_ui": "TASK_P3_10_NOT_STARTED",
        "p4_dynamic_replan": "DEFERRED",
        "production": "DEFAULT_DENY_NOT_READY",
    }
    assert report["issues"] == []


def test_ci_p3_planning_workspace_api_is_required_and_machine_checkable(
    tmp_path: Path,
) -> None:
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    normalized = " ".join(workflow.split())
    assert (
        "name: P3 planning workspace HTTP API evidence run: >- "
        "uv run python -m app.api.planning_workspace_check --root . "
        "--report build/validation/ci-p3-planning-workspace-api.json"
    ) in normalized
    assert "continue-on-error" not in workflow

    report_path = tmp_path / "p3-planning-workspace-api.json"
    assert (
        planning_workspace_api_main(["--root", str(ROOT), "--report", str(report_path)])
        == 0
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["report_version"] == "p3-planning-workspace-api-report.v1"
    assert report["status"] == "PASS"
    assert report["task_id"] == "TASK-P3-10"
    assert report["check_count"] == 8
    assert report["counts"]["api_paths"] == 18
    assert report["counts"]["successful_delegations"] == 18
    assert report["counts"]["production_provider_lookups"] == 0
    assert report["counts"]["router_business_state_transitions"] == 0
    assert report["boundaries"]["p4_capabilities"] == "NOT_IMPLEMENTED"
    assert report["boundaries"]["p4_additive_surface"] == (
        "OUTSIDE_FROZEN_P3_SUBSET"
    )
    assert report["boundaries"]["p3_10_frozen_operations"] == 17
    assert report["boundaries"]["p3_13_additive_operations"] == 1
    assert report["boundaries"]["internal_simulation_download"] == (
        "EXPORTED_VERIFIED_ZIP_ONLY"
    )
    assert report["boundaries"]["production_readiness"] == "NOT_CLAIMED"
    assert report["issues"] == []


def test_ci_p4_replanning_api_is_required_and_machine_checkable(
    tmp_path: Path,
) -> None:
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    normalized = " ".join(workflow.split())
    assert (
        "name: P4 dynamic replanning HTTP API evidence run: >- "
        "uv run python -m app.api.replanning_check --root . "
        "--report build/validation/ci-p4-replanning-api.json"
    ) in normalized
    assert "continue-on-error" not in workflow

    report_path = tmp_path / "p4-replanning-api.json"
    assert replanning_api_main(
        ["--root", str(ROOT), "--report", str(report_path)]
    ) == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["report_version"] == "p4-replanning-api-report.v1"
    assert report["status"] == "PASS"
    assert report["task_id"] == "TASK-P4-12"
    assert report["diff_base"] == "f4a54d3bb065b5cc8b51c450ffdc435bcc77d384"
    assert report["impact_rules"] == [
        "IMPACT-API",
        "IMPACT-DOCS",
        "IMPACT-FRONTEND",
        "IMPACT-INFRA",
        "IMPACT-TESTS",
    ]
    assert report["check_count"] == 8
    assert report["counts"]["api_paths"] == 8
    assert report["counts"]["http_operations"] == 9
    assert report["counts"]["successful_delegations"] == 9
    assert report["counts"]["p3_frozen_operations"] == 18
    assert report["counts"]["production_provider_lookups"] == 0
    assert report["counts"]["router_business_state_transitions"] == 0
    assert report["issues"] == []


def test_ci_benchmark_contract_is_xs_only_and_baseline_bound() -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert workflow.count("scripts/run_benchmark.py") == 1
    assert '--profile "${PLANTNEXUS_BENCHMARK_PROFILE}"' in workflow
    assert "PLANTNEXUS_BENCHMARK_PROFILE: xs" in workflow
    assert "--profile s" not in workflow
    assert "--profile m" not in workflow
    profile_set = load_profile_set(ROOT / "benchmarks" / "profiles.yaml")
    xs = profile_set.select("xs")
    baseline = load_baseline(ROOT / xs.baseline_path)
    assert xs.size == "XS"
    assert baseline["profile"] == {
        "profile_id": xs.profile_id,
        "profile_version": xs.profile_version,
        "size": xs.size,
    }
    assert baseline["boundaries"]["production_sla"] == ("NOT_ESTABLISHED_OPEN_012")


def test_ci_p2_vertical_slice_gate_is_required_and_machine_checkable(
    tmp_path: Path,
) -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    normalized = " ".join(workflow.split())
    assert (
        "name: P2 vertical slice Gate evidence run: >- uv run python -m "
        "app.application.p2_gate_report --root . --repeat 2 --report "
        "build/validation/ci-p2-vertical-slice-gate.json"
    ) in normalized
    assert "continue-on-error" not in workflow
    report_path = tmp_path / "p2-vertical-slice-gate.json"
    assert (
        p2_gate_main(
            [
                "--root",
                str(ROOT),
                "--repeat",
                "2",
                "--report",
                str(report_path),
            ]
        )
        == 0
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["report_version"] == "p2-vertical-slice-report.v1"
    assert report["status"] == "PASS"
    assert report["task_id"] == "TASK-P2-13"
    assert report["repeat_count"] == 2
    assert report["check_count"] == 11
    assert report["hash_consistency"]["unique_combined_fingerprints"] == 1
    assert report["counts"] == {
        "full_replays": 2,
        "correctness_scenario_executions": 14,
        "correctness_validator_passes": 14,
        "correctness_mutation_executions": 22,
        "unique_constraint_ids": 11,
        "benchmark_profile_executions": 6,
        "benchmark_global_measured_runs": 18,
        "benchmark_reference_measured_runs": 90,
        "benchmark_validator_passes": 108,
        "explicit_output_contract_executions": 2,
        "embedded_benchmark_export_executions": 6,
        "rejection_cases": 4,
    }
    assert report["blocking_gaps"] == []
    assert report["boundaries"]["exit_gate_decision"] == "NOT_PERFORMED"
    assert report["boundaries"]["p2_14"] == "NOT_STARTED"
    assert report["boundaries"]["p3"] == "NOT_STARTED"


def test_ci_p3_vertical_slice_gate_and_double_browser_replay_are_required() -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    normalized = " ".join(workflow.split())
    for fragment in (
        'name: P3 Gate Chromium replay 1 working-directory: frontend env: PLANTNEXUS_P3_GATE_REPLAY_INDEX: "1" run: npm exec -- playwright test --config playwright.p3-gate.config.ts',
        'name: P3 Gate Chromium replay 2 working-directory: frontend env: PLANTNEXUS_P3_GATE_REPLAY_INDEX: "2" run: npm exec -- playwright test --config playwright.p3-gate.config.ts',
        "node scripts/p3-gate-evidence.mjs --human-control-report ../build/validation/ci-p3-frontend.json --report ../build/validation/ci-p3-frontend-gate.json",
        "uv run python -m app.application.p3_gate_report --root . --repeat 2 --frontend-report build/validation/ci-p3-frontend-gate.json --p2-report build/validation/ci-p2-vertical-slice-gate.json --report build/validation/ci-p3-vertical-slice-gate.json",
    ):
        assert fragment in normalized
    assert workflow.index("P2 vertical slice Gate evidence") < workflow.index(
        "P3 vertical slice Gate evidence"
    )
    assert "build/validation/*.json" in workflow
    assert "build/playwright/**" in workflow
    assert "continue-on-error" not in workflow

    gate_source = (ROOT / "backend/app/application/p3_gate_report.py").read_text(
        encoding="utf-8"
    )
    frontend_source = (ROOT / "frontend/scripts/p3-gate-evidence.mjs").read_text(
        encoding="utf-8"
    )
    config_source = (ROOT / "frontend/playwright.p3-gate.config.ts").read_text(
        encoding="utf-8"
    )
    assert f'REPORT_VERSION = "{P3_GATE_REPORT_VERSION}"' in gate_source
    assert f'DIFF_BASE = "{P3_GATE_DIFF_BASE}"' in gate_source
    assert P3_FRONTEND_GATE_REPORT_VERSION in frontend_source
    assert "PLANTNEXUS_P3_GATE_REPLAY_INDEX" in config_source
    assert 'trace: "retain-on-failure"' in (
        ROOT / "frontend/playwright.config.ts"
    ).read_text(encoding="utf-8")


def test_ci_p4_vertical_slice_gate_and_double_browser_replay_are_required() -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    normalized = " ".join(workflow.split())
    for fragment in (
        'name: P4 Gate Chromium replay 1 working-directory: frontend env: PLANTNEXUS_P4_GATE_REPLAY_INDEX: "1" run: npm exec -- playwright test --config playwright.p4-gate.config.ts --workers=1',
        'name: P4 Gate Chromium replay 2 working-directory: frontend env: PLANTNEXUS_P4_GATE_REPLAY_INDEX: "2" run: npm exec -- playwright test --config playwright.p4-gate.config.ts --workers=1',
        "node scripts/p4-gate-evidence.mjs --replanning-report ../build/validation/ci-p4-replanning-frontend.json --report ../build/validation/ci-p4-frontend-gate.json",
        "uv run python -m app.application.p4_gate_report --root . --repeat 2 --frontend-report build/validation/ci-p4-frontend-gate.json --p2-report build/validation/ci-p2-vertical-slice-gate.json --p3-report build/validation/ci-p3-vertical-slice-gate.json --report build/validation/ci-p4-vertical-slice-gate.json",
    ):
        assert fragment in normalized
    assert workflow.index("P3 vertical slice Gate evidence") < workflow.index(
        "P4 vertical slice Gate evidence"
    )
    assert workflow.index("P4 Gate Frontend semantic evidence") < workflow.index(
        "P4 vertical slice Gate evidence"
    )
    assert "build/validation/*.json" in workflow
    assert "build/playwright/**" in workflow
    assert "continue-on-error" not in workflow

    gate_source = (ROOT / "backend/app/application/p4_gate_report.py").read_text(
        encoding="utf-8"
    )
    frontend_source = (ROOT / "frontend/scripts/p4-gate-evidence.mjs").read_text(
        encoding="utf-8"
    )
    config_source = (ROOT / "frontend/playwright.p4-gate.config.ts").read_text(
        encoding="utf-8"
    )
    assert f'REPORT_VERSION = "{P4_GATE_REPORT_VERSION}"' in gate_source
    assert f'DIFF_BASE = "{P4_GATE_DIFF_BASE}"' in gate_source
    assert P4_FRONTEND_GATE_REPORT_VERSION in frontend_source
    assert "PLANTNEXUS_P4_GATE_REPLAY_INDEX" in config_source
    assert 'trace: "retain-on-failure"' in (
        ROOT / "frontend/playwright.config.ts"
    ).read_text(encoding="utf-8")


def test_ci_p5_empty_selected_portfolio_gate_is_required_and_machine_checkable() -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    normalized = " ".join(workflow.split())
    assert (
        "uv run python -m app.application.p5_portfolio_gate_report --root . "
        "--repeat 2 --portfolio-manifest docs/core/p5-portfolio-amendment-manifest.md "
        "--frontend-report build/validation/ci-p4-frontend-gate.json "
        "--p2-report build/validation/ci-p2-vertical-slice-gate.json "
        "--p3-report build/validation/ci-p3-vertical-slice-gate.json "
        "--report build/validation/ci-p5-portfolio-gate.json"
    ) in normalized
    p4_command = "uv run python -m app.application.p4_gate_report"
    p5_command = "uv run python -m app.application.p5_portfolio_gate_report"
    assert workflow.index(p4_command) < workflow.index(p5_command)
    assert workflow.index(p5_command) < workflow.index("Build package")
    assert "build/validation/*.json" in workflow
    assert "continue-on-error" not in workflow

    gate_source = (
        ROOT / "backend/app/application/p5_portfolio_gate_report.py"
    ).read_text(encoding="utf-8")
    assert f'REPORT_VERSION = "{P5_GATE_REPORT_VERSION}"' in gate_source
    assert f'DIFF_BASE = "{P5_GATE_DIFF_BASE}"' in gate_source
    assert "P5-03～20" not in workflow


def test_ci_p5_exit_gate_is_independent_required_and_machine_checkable() -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )
    normalized = " ".join(workflow.split())
    qualification = (
        "name: P5 capability qualification fresh evidence run: >- uv run python "
        "scripts/p5_capability_qualification.py --root . --manifest "
        "fixtures/simulation/p5/qualification/evidence-manifest.v1.json --report "
        "build/validation/ci-p5-capability-qualification.json"
    )
    expected = (
        "name: P5 Exit Gate independent audit evidence run: >- uv run python -m "
        "app.application.p5_exit_gate_audit --root . --provider-observation "
        "docs/p5-exit-gate-audit-observations.v1.json --qualification-report "
        "build/validation/ci-p5-capability-qualification.json --p5-gate-report "
        "build/validation/ci-p5-portfolio-gate.json --p4-gate-report "
        "build/validation/ci-p4-vertical-slice-gate.json --p4-exit-observation "
        "docs/p4-exit-gate-audit-observations.v1.json --report "
        "build/validation/ci-p5-exit-gate-audit.json"
    )
    assert qualification in normalized
    assert expected in normalized
    assert workflow.index("app.application.p5_portfolio_gate_report") < workflow.index(
        "scripts/p5_capability_qualification.py"
    )
    assert workflow.index("scripts/p5_capability_qualification.py") < workflow.index(
        "app.application.p5_exit_gate_audit"
    )
    assert workflow.index("app.application.p5_exit_gate_audit") < workflow.index(
        "Build package"
    )
    assert "continue-on-error" not in workflow
    source = (ROOT / "backend/app/application/p5_exit_gate_audit.py").read_text(
        encoding="utf-8"
    )
    assert f'REPORT_VERSION = "{P5_EXIT_REPORT_VERSION}"' in source
    assert f'DIFF_BASE = "{P5_EXIT_DIFF_BASE}"' in source


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
    assert report["schema_set_version"] == "2.10.0"
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
    assert report["schema_set_version"] == "2.10.0"
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
    assert temporal_model_main(["--root", str(ROOT), "--report", str(report_path)]) == 0
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
    assert report["boundaries"]["benchmark"] == ("MODEL_DELTA_ONLY_NO_XS_S_M_BASELINE")


def test_ci_cp_sat_fact_lock_model_report_is_machine_checkable(
    tmp_path: Path,
) -> None:
    report_path = tmp_path / "cp-sat-fact-lock-model.json"
    assert (
        fact_lock_model_main(["--root", str(ROOT), "--report", str(report_path)]) == 0
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
        objective_strategy_main(["--root", str(ROOT), "--report", str(report_path)])
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


def test_ci_p2_correctness_report_is_machine_checkable(tmp_path: Path) -> None:
    report_path = tmp_path / "p2-correctness.json"
    assert p2_correctness_main(["--root", str(ROOT), "--report", str(report_path)]) == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))

    assert report["report_version"] == "p2-correctness-report.v1"
    assert report["status"] == "PASS"
    assert report["task_id"] == "TASK-P2-09"
    assert report["check_count"] == 8
    assert report["counts"] == {
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
    assert {check["name"] for check in report["checks"]} == {
        "frozen-schema-problem-strategy-validator-policy-generator-and-lock",
        "p0-p1-immutable-asset-manifest",
        "seven-versioned-profile-scenario-blueprint-manifest-assets",
        "formal-ingress-snapshot-problem-replay",
        "golden-jssp-fjsp-manual-optimum-and-validator",
        "five-scenario-correctness-matrix",
        "solver-generated-property-and-reordering-replay",
        "formula-free-exact-c001-c011-validator-mutations",
    }
    assert report["boundaries"] == {
        "data_plane": "SIMULATION_ONLY",
        "formal_path": (
            "RAW_STAGING_TO_IMPORT_V2_TO_QUALITY_TO_EXPANSION_TO_"
            "SNAPSHOT_V2_TO_PROBLEM_V2_TO_GLOBAL_STRATEGY_TO_VALIDATOR"
        ),
        "direct_problem_or_cp_model_construction": "NONE",
        "schema_contract_changes": "NONE",
        "planning_solver_validator_semantic_changes": "NONE",
        "dependency_changes": "NONE",
        "performance_baseline": "NONE_NO_XS_S_M",
        "production_authority": "NOT_CLAIMED",
        "reference_export_benchmark": "NOT_IMPLEMENTED_BY_TASK",
        "p2_10_plus_or_p3": "NOT_STARTED",
    }


def test_ci_reference_scheduler_report_is_machine_checkable(tmp_path: Path) -> None:
    report_path = tmp_path / "reference-schedulers.json"
    assert (
        reference_scheduler_main(["--root", str(ROOT), "--report", str(report_path)])
        == 0
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))

    assert report["report_version"] == "reference-scheduler-report.v1"
    assert report["status"] == "PASS"
    assert report["task_id"] == "TASK-P2-10"
    assert report["contract_version"] == "reference-scheduler-contracts.v1"
    assert report["policy_version"] == "reference-scheduler-policy.v1"
    assert report["check_count"] == 7
    assert report["counts"] == {
        "algorithms": 5,
        "scenario_cases": 7,
        "complete_candidates": 35,
        "independent_validator_passes": 35,
        "deterministic_replays": 35,
        "heuristic_failure_cases": 5,
    }
    assert {check["name"] for check in report["checks"]} == {
        "frozen-problem-solution-kpi-validator-rule-correctness-and-lock",
        "five-versioned-algorithm-identities-and-exact-tie-breaks",
        "seven-authoritative-p2-correctness-problems",
        "complete-candidates-across-all-reference-algorithms",
        "fresh-formal-validator-and-shared-kpi-measurement",
        "deterministic-replay-and-explicit-heuristic-failure",
        "non-production-and-comparison-boundary",
    }
    assert [value["algorithm_id"] for value in report["algorithms"]] == [
        "reference-fcfs.v1",
        "reference-edd.v1",
        "reference-spt.v1",
        "reference-priority-edd.v1",
        "reference-greedy-earliest-available-machine.v1",
    ]
    assert len(report["scenario_results"]) == 35
    assert all(value["status"] == "FEASIBLE" for value in report["scenario_results"])
    assert all(
        value["validation_status"] == "PASS" and value["hard_violation_count"] == 0
        for value in report["scenario_results"]
    )
    assert report["boundaries"] == {
        "data_plane": "SIMULATION_ONLY",
        "problem_contract": "PLANNING_PROBLEM_V2_UNCHANGED",
        "hard_constraints": "C_001_THROUGH_C_011_FORMAL_VALIDATOR",
        "candidate_policy": "COMPLETE_OR_DISCARDED",
        "random_or_partial_schedule": "PROHIBITED",
        "heuristic_failure_is_infeasibility_certificate": False,
        "production_fallback": "PROHIBITED",
        "global_comparison": "DEFERRED_TO_TASK_P2_12",
        "benchmark_profiles_thresholds": "NOT_STARTED",
        "p2_11_plus_or_p3": "NOT_STARTED",
    }


def test_ci_p2_output_contract_report_is_machine_checkable(tmp_path: Path) -> None:
    report_path = tmp_path / "p2-output-contracts.json"
    assert (
        output_contract_main(["--root", str(ROOT), "--report", str(report_path)]) == 0
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))

    assert report["report_version"] == "p2-output-contract-report.v1"
    assert report["status"] == "PASS"
    assert report["task_id"] == "TASK-P2-11"
    assert report["schema_set_version"] == "2.5.0"
    assert report["package_profile"] == "p2-internal-export.v1"
    assert report["check_count"] == 8
    assert report["counts"] == {
        "package_files_excluding_manifest": 9,
        "assignments": 4,
        "demands": 2,
        "resources": 2,
        "rejection_cases": 3,
        "deterministic_replays": 2,
    }
    assert {check["name"] for check in report["checks"]} == {
        "frozen-input-contracts-new-schemas-samples-and-lock",
        "kpi-v2-and-export-manifest-draft-2020-12-roundtrip",
        "validated-solution-kpi-and-solver-report-freeze",
        "deterministic-package-bytes-file-hashes-and-row-counts",
        "cross-file-run-hash-version-and-entity-count-lineage",
        "validator-fail-mixed-lineage-and-tamper-rejections",
        "atomic-write-exact-replay-and-partial-cleanup",
        "p2-internal-non-publishable-state-and-deferred-boundary",
    }
    assert report["boundaries"] == {
        "data_plane": "SIMULATION_ONLY",
        "schedule_carrier": "VALIDATED_PLANNING_SOLUTION_NOT_SCHEDULE_VERSION",
        "export_job": "NOT_CREATED",
        "approval_publish_external_transfer": "PROHIBITED",
        "change_report": "DEFERRED_P4_DYNAMIC_REPLAN",
        "benchmark_report": "DEFERRED_P2_12",
        "p2_12_plus_or_p3": "NOT_STARTED",
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


def test_p3_i18n_wire_freeze_allows_additive_future_phase_contracts() -> None:
    source = (ROOT / "frontend" / "scripts" / "i18n-evidence.mjs").read_text(
        encoding="utf-8"
    )
    for exact_path in (
        "frontend/src/api",
        "frontend/package.json",
        "frontend/package-lock.json",
        "backend/app/api/dependencies/__init__.py",
        "backend/app/api/routers/planning_workspace.py",
        "schemas/json/schedule-version.schema.json",
        "schemas/json/workspace-command.schema.json",
        "schemas/json/workspace-query.schema.json",
        "schemas/rules/error-code-registry.v2.yaml",
        "schemas/rules/state-machines.v1.yaml",
        "uv.lock",
    ):
        assert f'"{exact_path}"' in source
    for additive_phase_composition_path in (
        "backend/app/api/__init__.py",
        "backend/app/api/app.py",
        "backend/app/api/contracts.py",
        "backend/app/api/dependencies/authorization.py",
        "backend/app/api/planning_workspace_check.py",
        "backend/app/api/routers/__init__.py",
    ):
        assert f'"{additive_phase_composition_path}"' not in source
    for stale_broad_path in ('"backend"', '"schemas"', '"pyproject.toml"'):
        assert stale_broad_path not in source
