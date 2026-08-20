"""Reproducible dependency, container, and phase-aware CI contract checks."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any, cast

import yaml

from app.planning.problem.contract_check import main as problem_contract_main

ROOT = Path(__file__).resolve().parents[3]

EXPECTED_RUNTIME_DEPENDENCIES = {
    "alembic==1.16.5",
    "celery==5.5.3",
    "defusedxml==0.7.1",
    "fastapi==0.116.1",
    "openpyxl==3.1.5",
    "opentelemetry-api==1.36.0",
    "psycopg[binary]==3.2.9",
    "pydantic-settings==2.10.1",
    "redis==6.4.0",
    "sqlalchemy==2.0.43",
    "structlog==25.4.0",
    "uvicorn==0.35.0",
}
PHASE_GOVERNANCE_TEST_ID = "TEST-PHASE-GOVERNANCE-001"


def test_runtime_dependencies_are_exact_and_solver_free() -> None:
    project = cast(
        dict[str, Any],
        tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8")),
    )
    dependencies = set(cast(list[str], project["project"]["dependencies"]))
    assert dependencies == EXPECTED_RUNTIME_DEPENDENCIES
    assert all("ortools" not in dependency.lower() for dependency in dependencies)
    lock_text = (ROOT / "uv.lock").read_text(encoding="utf-8").lower()
    assert "name = \"ortools\"" not in lock_text


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
    assert "PLANTNEXUS_POSTGRES_PASSWORD" in services["database"]["environment"][
        "POSTGRES_PASSWORD"
    ]


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
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )
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
    assert "ortools" not in workflow.lower()
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
        problem_contract_main(
            ["--root", str(ROOT), "--report", str(report_path)]
        )
        == 0
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))

    assert report["report_version"] == "planning-problem-contract-report.v1"
    assert report["status"] == "PASS"
    assert report["task_id"] == "TASK-P2-01"
    assert report["schema_set_version"] == "2.3.0"
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


def test_container_build_is_pinned_and_non_root() -> None:
    dockerfile = (ROOT / "infra" / "Dockerfile").read_text(encoding="utf-8")
    assert dockerfile.startswith("FROM python:3.12.13-slim-bookworm\n")
    assert "uv==0.11.32" in dockerfile
    assert "uv sync --locked --no-dev --no-editable" in dockerfile
    assert "USER plantnexus" in dockerfile
    assert "app.api.app:app" in dockerfile
