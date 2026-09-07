"""Integration evidence for P8-10 CLI, Compose, and report boundaries."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, cast

import yaml

from scripts.p8_operations_check import main

ROOT = Path(__file__).resolve().parents[3]


def test_contract_cli_writes_four_distinct_machine_reports() -> None:
    evidence_root = ROOT / "build" / "validation"
    evidence_root.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="p8-operations-test-", dir=evidence_root) as temp:
        paths = [Path(temp) / f"report-{index}.json" for index in range(4)]
        assert (
            main(
                [
                    "--root",
                    str(ROOT),
                    "--contract-only",
                    "--deployment-report",
                    str(paths[0]),
                    "--observability-report",
                    str(paths[1]),
                    "--recovery-report",
                    str(paths[2]),
                    "--runbook-report",
                    str(paths[3]),
                ]
            )
            == 0
        )
        reports = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    assert [report["report_version"] for report in reports] == [
        "p8-operations-deployment-report.v1",
        "p8-operations-observability-report.v1",
        "p8-operations-recovery-report.v1",
        "p8-operations-runbook-dry-run-report.v1",
    ]
    assert all(report["task_id"] == "TASK-P8-10" for report in reports)
    assert all(report["test_id"] == "TEST-P8-OPERATIONS-001" for report in reports)
    assert all(report["status"] == "PASS" for report in reports)


def test_operations_compose_adds_pinned_isolated_services() -> None:
    document = cast(
        dict[str, Any],
        yaml.safe_load(
            (ROOT / "infra/operations/compose.p8-operations.yml").read_text(
                encoding="utf-8"
            )
        ),
    )
    services = cast(dict[str, Any], document["services"])
    assert set(services) == {
        "api",
        "database",
        "migrate",
        "observer",
        "redis",
        "rollback_api",
        "rollback_worker",
        "validator",
        "worker",
    }
    assert "@sha256:" in services["database"]["image"]
    assert "@sha256:" in services["redis"]["image"]
    for service in (
        "api",
        "worker",
        "migrate",
        "validator",
        "rollback_api",
        "rollback_worker",
    ):
        environment = cast(dict[str, str], services[service]["environment"])
        assert environment["PLANTNEXUS_RUNTIME_ENVIRONMENT"] == "test"
        assert environment["PLANTNEXUS_DATA_PLANE"] == "simulation"
        assert environment["PLANTNEXUS_RUNTIME_COMPOSITION_ENABLED"] == "true"
        assert environment["PLANTNEXUS_SIMULATION_API_ENABLED"] == "true"
    assert services["api"]["healthcheck"]["test"][-1].endswith(
        "/health/ready', timeout=2)"
    )
    assert services["rollback_api"]["ports"] == ["127.0.0.1:8001:8000"]
    assert services["worker"]["command"][-2:] == [
        "--concurrency=1",
        "--hostname=candidate@p8-operations",
    ]
    assert services["rollback_worker"]["command"][-2:] == [
        "--concurrency=1",
        "--hostname=rollback@p8-operations",
    ]
