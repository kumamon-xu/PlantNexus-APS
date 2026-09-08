"""Contract evidence for TEST-P8-PLUGIN-REGISTRY-001."""

from __future__ import annotations

from collections.abc import Mapping
import json
from pathlib import Path

from aps_extension_sdk import (
    ConstraintOutput,
    ObjectiveOutput,
    PlanningRuleOutput,
    ReplanAction,
    ValidationOutput,
)

from backend.tests.p8_runtime_extension_support import runtime_extension_fixture
from scripts.p8_runtime_extension_registry_check import main as registry_check_main


def _fixture(tmp_path: Path):
    return runtime_extension_fixture(
        tmp_path,
        database_url=f"sqlite:///{(tmp_path / 'contract.db').as_posix()}",
    )


def _input() -> dict[str, Mapping[str, object]]:
    return {
        "scope": {
            "tenant_id": "TENANT-P8-EXTENSION",
            "factory_id": "FACTORY-P8-EXTENSION",
            "planning_scope_id": "PLANNING-P8-EXTENSION",
        },
        "facts": {"candidate_count": 2, "synthetic": True},
        "provenance": {"planning_run_id": "planning-run-p8-extension"},
    }


def test_loader_commits_exact_allow_list_and_safe_fingerprints(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    adapter = fixture.load()
    document = adapter.document
    reference = adapter.extension_set_reference

    assert document["adapter_version"] == "runtime-extension-adapter.v2"
    assert document["mode"] == "LOADED"
    assert document["load_policy"] == "BUILD_DEPLOY_STARTUP_ONLY"
    assert document["trusted_in_process"] is True
    assert document["sandboxed"] is False
    assert document["sdk_api_version"] == "1.0.0"
    assert document["registry_protocol_version"] == "plugin-registry.v1"
    assert document["extension_count"] == 1
    assert document["contribution_count"] == 7
    assert document["catalog_fingerprint"] == fixture.catalog["catalog_fingerprint"]
    assert reference == {
        "extension_set_id": reference["extension_set_id"],
        "extension_set_fingerprint": document["extension_set_fingerprint"],
        "configuration_fingerprint": fixture.catalog["catalog_fingerprint"],
    }
    rendered = str(document)
    assert str(tmp_path) not in rendered
    assert "verification-key-material" not in rendered
    assert "sqlite://" not in rendered


def test_all_six_spi_are_invoked_through_frozen_atomic_adapters(tmp_path: Path) -> None:
    adapter = _fixture(tmp_path).load()
    values = _input()
    common = {
        "scope": values["scope"],
        "facts": values["facts"],
        "provenance": values["provenance"],
    }

    constraints = adapter.invoke_constraints(**common)
    objectives = adapter.invoke_objectives(**common)
    planning_rules = adapter.invoke_planning_rules(**common)
    validations = adapter.invoke_validation_rules(**common)
    replan = adapter.invoke_replan_policy(
        **common,
        execution_fact_fingerprint=f"sha256:{'1' * 64}",
        hard_lock_fingerprint=f"sha256:{'2' * 64}",
        freeze_window_fingerprint=f"sha256:{'3' * 64}",
        state_machine_version="planning.run.state.v1",
        publication_authority_reference="authority.synthetic",
    )
    registry = adapter.invoke_plugin_registry()

    assert len(constraints) == 1 and isinstance(constraints[0], ConstraintOutput)
    assert len(objectives) == 1 and isinstance(objectives[0], ObjectiveOutput)
    assert len(planning_rules) == 1 and isinstance(
        planning_rules[0], PlanningRuleOutput
    )
    assert len(validations) == 2 and all(
        isinstance(item, ValidationOutput) and item.passed for item in validations
    )
    assert replan is not None and replan.action is ReplanAction.NO_REPLAN
    assert registry == adapter.registry.resolution
    metrics = adapter.safe_metrics()
    assert metrics["payloads_recorded"] is False
    assert metrics["exception_details_recorded"] is False
    assert {row["extension_point"] for row in metrics["contributions"]} == {
        "CONSTRAINT",
        "OBJECTIVE",
        "PLANNING_RULE",
        "PLUGIN_REGISTRY",
        "REPLAN_POLICY",
        "VALIDATION_RULE",
    }


def test_configuration_is_copied_into_sdk_view_without_mutable_alias(
    tmp_path: Path,
) -> None:
    values: dict[str, object] = {"nested": {"mode": "ORIGINAL"}}
    fixture = runtime_extension_fixture(
        tmp_path,
        database_url=f"sqlite:///{(tmp_path / 'immutable.db').as_posix()}",
        configuration_values=values,
    )
    adapter = fixture.load()
    values["nested"] = {"mode": "MUTATED"}
    result = adapter.invoke_constraints(**_input())
    assert len(result) == 1
    assert adapter.registry.bindings[0].configuration["values"] == {
        "nested": {"mode": "ORIGINAL"}
    }


def test_machine_reports_bind_task_resolution_security_and_metrics(
    tmp_path: Path,
) -> None:
    report_path = tmp_path / "registry-report.json"
    manifest_path = tmp_path / "resolution-manifest.json"
    security_path = tmp_path / "security-report.json"
    benchmark_path = tmp_path / "benchmark-report.json"
    root = Path(__file__).resolve().parents[3]
    assert (
        registry_check_main(
            [
                "--root",
                str(root),
                "--report",
                str(report_path),
                "--manifest",
                str(manifest_path),
                "--security-report",
                str(security_path),
                "--benchmark-report",
                str(benchmark_path),
            ]
        )
        == 0
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    security = json.loads(security_path.read_text(encoding="utf-8"))
    benchmark = json.loads(benchmark_path.read_text(encoding="utf-8"))
    assert report["task_id"] == "TASK-P8-13"
    assert report["test_id"] == "TEST-P8-PLUGIN-REGISTRY-001"
    assert report["diff_base"] == "4d37dba068c86230f6009820d6cbc7ff10a73495"
    assert report["check_count"] == 10
    assert report["negative_count"] == 13
    assert report["issues"] == []
    assert report["status"] == "PASS"
    assert manifest["status"] == security["status"] == benchmark["status"] == "PASS"
    assert len(manifest["contributions"]) == 7
    assert all(security["negative_matrix"].values())
    assert benchmark["thresholds"] is None
