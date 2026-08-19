"""TASK-P0-08 reproducible dependency, container, and CI configuration checks."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any, cast

import yaml

ROOT = Path(__file__).resolve().parents[3]

EXPECTED_RUNTIME_DEPENDENCIES = {
    "alembic==1.16.5",
    "celery==5.5.3",
    "fastapi==0.116.1",
    "opentelemetry-api==1.36.0",
    "psycopg[binary]==3.2.9",
    "pydantic-settings==2.10.1",
    "redis==6.4.0",
    "sqlalchemy==2.0.43",
    "structlog==25.4.0",
    "uvicorn==0.35.0",
}


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


def test_ci_runs_all_p0_gates_and_keeps_benchmark_as_a_hook() -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )
    required_fragments = (
        "uv sync --locked",
        "uv run ruff check .",
        "uv run pyright backend/app backend/tests",
        "backend/tests/integration",
        "app.infrastructure.contract_check",
        "docker compose --env-file .env.example config --quiet",
        "scripts/check_docs.py --task",
        "uv build",
        "PLANTNEXUS_BENCHMARK_PROFILE: pr",
    )
    for fragment in required_fragments:
        assert fragment in workflow
    assert "ortools" not in workflow.lower()
    assert "scripts/run_benchmark.py" in workflow
    assert "actions/upload-artifact@v4" in workflow


def test_container_build_is_pinned_and_non_root() -> None:
    dockerfile = (ROOT / "infra" / "Dockerfile").read_text(encoding="utf-8")
    assert dockerfile.startswith("FROM python:3.12.13-slim-bookworm\n")
    assert "uv==0.11.32" in dockerfile
    assert "uv sync --locked --no-dev --no-editable" in dockerfile
    assert "USER plantnexus" in dockerfile
    assert "app.api.app:app" in dockerfile
