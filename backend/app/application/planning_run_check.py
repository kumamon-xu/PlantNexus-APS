"""Emit deterministic TASK-P8-04 orchestration contract evidence."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, cast

import yaml

from app.domain.planning_run import (
    ATTEMPT_TRANSITIONS,
    PLANNING_RUN_STATES,
    PLANNING_RUN_TERMINAL_STATES,
    PLANNING_RUN_TRANSITIONS,
)


REPORT_VERSION = "p8-planning-run-orchestration-report.v1"
TASK_ID = "TASK-P8-04"
TEST_ID = "TEST-P8-PLANNING-RUN-001"
DIFF_BASE = "29000eeaf73fb1306f1bcb6f7cb7ab761283d682"
MIGRATION_HEAD = "0007_planning_run_orchestration"
REQUIRED_TABLES = (
    "planning_runs",
    "planning_run_attempts",
    "planning_run_work_items",
    "planning_run_audit_records",
    "planning_run_transitions",
    "planning_run_command_records",
)


def _planning_run_registry(root: Path) -> dict[str, Any]:
    document = cast(
        dict[str, Any],
        yaml.safe_load(
            (root / "schemas/rules/state-machines.v1.yaml").read_text(encoding="utf-8")
        ),
    )
    return cast(
        dict[str, Any],
        next(
            machine
            for machine in document["machines"]
            if machine["machine"] == "PLANNING_RUN"
        ),
    )


def run_checks(root: Path) -> dict[str, object]:
    """Inspect frozen registry parity and the additive persistence boundary."""

    registry = _planning_run_registry(root)
    registry_pairs = {
        (cast(str, item["from"]), cast(str, item["to"]))
        for item in registry["transitions"]
    }
    migration_path = (
        root / "backend/migrations/versions/0007_planning_run_orchestration.py"
    )
    migration_text = migration_path.read_text(encoding="utf-8")
    integration_test_text = (
        root / "backend/tests/integration/test_p8_planning_run_repository.py"
    ).read_text(encoding="utf-8")
    schema_path = root / "schemas/json/planning-run.schema.json"
    checks = {
        "frozen_state_parity": PLANNING_RUN_STATES == frozenset(registry["states"]),
        "frozen_terminal_parity": PLANNING_RUN_TERMINAL_STATES
        == frozenset(registry["terminal_states"]),
        "frozen_pair_parity": PLANNING_RUN_TRANSITIONS == registry_pairs,
        "state_count_16": len(PLANNING_RUN_STATES) == 16,
        "transition_count_31": len(PLANNING_RUN_TRANSITIONS) == 31,
        "no_self_transition": all(
            source != target for source, target in PLANNING_RUN_TRANSITIONS
        ),
        "no_terminal_source_transition": all(
            source not in PLANNING_RUN_TERMINAL_STATES
            for source, _target in PLANNING_RUN_TRANSITIONS
        ),
        "attempt_machine_has_no_self_transition": all(
            source != target for source, target in ATTEMPT_TRANSITIONS
        ),
        "migration_chain_is_additive": (
            'down_revision: str | None = "0006_canonical_ingress_application"'
            in migration_text
        ),
        "required_tables_declared": all(
            f'"{table}"' in migration_text for table in REQUIRED_TABLES
        ),
        "queue_is_not_delivered_here": "celery" not in migration_text.lower()
        and "redis" not in migration_text.lower(),
        "command_latency_is_observation_only": (
            "perf_counter_ns" in integration_test_text
            and "DEVELOPMENT_OBSERVATION_NO_SLA" in integration_test_text
            and "p8_transition_elapsed_us" in integration_test_text
        ),
    }
    issues = sorted(name for name, passed in checks.items() if not passed)
    return {
        "report_version": REPORT_VERSION,
        "task_id": TASK_ID,
        "test_id": TEST_ID,
        "diff_base": DIFF_BASE,
        "validation_profile": "HIGH_RISK",
        "migration_head": MIGRATION_HEAD,
        "status": "PASS" if not issues else "FAIL",
        "checks": checks,
        "counts": {
            "planning_run_states": len(PLANNING_RUN_STATES),
            "planning_run_terminal_states": len(PLANNING_RUN_TERMINAL_STATES),
            "planning_run_transitions": len(PLANNING_RUN_TRANSITIONS),
            "attempt_transitions": len(ATTEMPT_TRANSITIONS),
            "persistence_tables": len(REQUIRED_TABLES),
        },
        "frozen_inputs": {
            "state_registry": "state-machines.v1",
            "planning_run_schema_sha256": sha256(schema_path.read_bytes()).hexdigest(),
        },
        "production_boundary": {
            "worker_delivery": "NOT_IMPLEMENTED_P8_05",
            "solver_execution": "NOT_IMPLEMENTED_P8_05",
            "headless_http": "NOT_IMPLEMENTED_P8_07",
            "demo": "EXCLUDED",
        },
        "engineering_observation": {
            "carrier": "pytest-junit-testsuite-properties",
            "metrics": [
                "p8_materialize_elapsed_us",
                "p8_read_elapsed_us",
                "p8_transition_elapsed_us",
            ],
            "threshold": None,
            "semantics": "DEVELOPMENT_OBSERVATION_NO_SLA",
        },
        "issues": issues,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    report = run_checks(arguments.root.resolve())
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if arguments.output is not None:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
