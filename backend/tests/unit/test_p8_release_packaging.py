"""Pure version, dependency, SBOM, and migration tests for P8-09."""

from __future__ import annotations

import tomllib

from app import APPLICATION_VERSION, CORE_VERSION, RUNTIME_VERSION, SCHEMA_VERSION, SPEC_VERSION
from app.infrastructure.release.builder import (
    build_license_report,
    build_migration_manifest,
    build_sbom,
    load_release_policy,
    runtime_dependency_graph,
)
from backend.tests.p8_release_support import ROOT, TEST_EPOCH


def test_runtime_application_core_and_contract_versions_are_explicit() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    versions = project["tool"]["plantnexus-aps"]["versions"]
    assert SPEC_VERSION == "0.3.0"
    assert SCHEMA_VERSION == "2.10.0"
    assert APPLICATION_VERSION == CORE_VERSION == "0.0.0"
    assert RUNTIME_VERSION == "0.1.0"
    assert versions == {
        "spec": SPEC_VERSION,
        "schema": SCHEMA_VERSION,
        "code": APPLICATION_VERSION,
        "application": APPLICATION_VERSION,
        "core": CORE_VERSION,
        "runtime": RUNTIME_VERSION,
    }


def test_runtime_dependency_graph_is_exact_and_excludes_dev_group() -> None:
    lock = (ROOT / "uv.lock").read_bytes()
    packages, graph = runtime_dependency_graph(lock)
    assert len(packages) == len(graph) == 51
    assert "plantnexus-aps" in packages
    assert "psycopg-binary" in packages
    assert "httpx" not in packages
    assert "pytest" not in packages
    assert graph["plantnexus-aps"] == {
        "alembic",
        "celery",
        "defusedxml",
        "fastapi",
        "openpyxl",
        "opentelemetry-api",
        "ortools",
        "psycopg",
        "pydantic-settings",
        "redis",
        "sqlalchemy",
        "structlog",
        "uvicorn",
    }


def test_license_inventory_and_cyclonedx_are_deterministic() -> None:
    lock = (ROOT / "uv.lock").read_bytes()
    packages, graph = runtime_dependency_graph(lock)
    policy = load_release_policy(ROOT)
    licenses = build_license_report(packages, policy)
    first = build_sbom(
        packages,
        graph,
        lock_bytes=lock,
        epoch=TEST_EPOCH,
        licenses=licenses,
        target=policy["target"],
    )
    second = build_sbom(
        packages,
        graph,
        lock_bytes=lock,
        epoch=TEST_EPOCH,
        licenses=licenses,
        target=policy["target"],
    )
    assert licenses["status"] == "PASS"
    assert licenses["component_count"] == 51
    assert first == second
    assert first["bomFormat"] == "CycloneDX"
    assert first["specVersion"] == "1.5"
    assert len(first["components"]) == 51


def test_migration_manifest_is_one_immutable_linear_chain() -> None:
    manifest = build_migration_manifest(
        ROOT, database_head="0009_host_authorization_audit"
    )
    chain = manifest["linear_chain"]
    assert manifest["revision_count"] == len(chain) == 9
    assert chain[0]["revision"] == "0001_engineering_job_metadata"
    assert chain[-1]["revision"] == "0009_host_authorization_audit"
    assert all(
        row["downgrade_data_boundary"]
        == "POTENTIALLY_DESTRUCTIVE_REQUIRES_BACKUP"
        for row in chain
    )
    assert manifest["rollback"] == {
        "automatic_production_downgrade": False,
        "backup_required": True,
        "strategy": "BACKUP_RESTORE_OR_APPROVED_FORWARD_FIX",
    }
