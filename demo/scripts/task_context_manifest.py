"""Create the Demo-local task-context-manifest without registering a P7 task."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path


DEMO_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = DEMO_ROOT.parent

FOUNDATION_INPUTS = (
    ("docs/contracts/import-and-normalization.md", "FULL"),
    ("docs/contracts/planning-snapshot.md", "FULL"),
    ("docs/contracts/planning-problem.md", "FULL"),
    ("docs/contracts/planning-policy-and-solve-limits.md", "FULL"),
    ("docs/contracts/execution-events-and-replan-request.md", "FULL"),
    ("docs/adr/ADR-0001-simulation-first-common-ingress.md", "FULL"),
    ("docs/adr/ADR-0005-independent-schedule-validator.md", "FULL"),
    ("docs/adr/ADR-0008-utc-seconds-and-solver-ticks.md", "FULL"),
    ("docs/adr/ADR-0010-planning-problem-v2-contract-evolution.md", "FULL"),
    ("docs/adr/ADR-0011-ortools-9-15-cp-sat-backend-version-policy.md", "FULL"),
    ("docs/adr/ADR-0013-execution-event-authority-fact-projection-replan-lineage.md", "FULL"),
    ("docs/adr/ADR-0014-freeze-window-stability-change-report.md", "FULL"),
    ("docs/simulation/synthetic-generator-and-determinism.md", "FULL"),
    ("docs/simulation/benchmark-harness.md", "FULL"),
    ("docs/simulation/performance-gates.md", "FULL"),
)

SELECTED_INPUTS_BY_TASK = {
    "TASK-DEMO-01": (
        ("demo/docs/TASK-DEMO-01-cnc-demo-foundation-and-benchmark-gate.md", "FULL"),
        ("demo/docs/02-cnc-data-design.md", "FULL"),
        ("demo/docs/05-benchmark-and-acceptance.md", "FULL"),
        *FOUNDATION_INPUTS,
    ),
    "TASK-DEMO-02": (
        ("demo/docs/TASK-DEMO-02-durable-runtime-initial-plan-and-baseline.md", "FULL"),
        ("demo/docs/03-architecture-and-api.md", "FULL"),
        ("demo/docs/TASKS.md", "FULL"),
        ("docs/contracts/planning-workspace-api.md", "FULL"),
        ("docs/contracts/planning-solution-and-schedule-version.md", "FULL"),
        ("docs/contracts/authorization-and-audit.md", "FULL"),
        ("docs/contracts/execution-events-and-replan-request.md", "FULL"),
        ("docs/adr/ADR-0005-independent-schedule-validator.md", "FULL"),
        ("docs/adr/ADR-0010-planning-problem-v2-contract-evolution.md", "FULL"),
        ("docs/adr/ADR-0013-execution-event-authority-fact-projection-replan-lineage.md", "FULL"),
        ("docs/adr/ADR-0014-freeze-window-stability-change-report.md", "FULL"),
        ("backend/app/api/app.py", "FULL"),
        ("backend/app/application/schedule_versions.py", "FULL"),
        ("backend/app/application/approval.py", "FULL"),
        ("backend/app/application/publication.py", "FULL"),
        ("backend/app/infrastructure/workspace_persistence.py", "FULL"),
    ),
    "TASK-DEMO-03": (
        ("demo/docs/TASK-DEMO-03-urgent-order-and-dynamic-replan.md", "FULL"),
        ("demo/docs/02-cnc-data-design.md", "FULL"),
        ("demo/docs/03-architecture-and-api.md", "FULL"),
        ("demo/docs/05-benchmark-and-acceptance.md", "FULL"),
        ("demo/docs/TASKS.md", "FULL"),
        ("docs/contracts/import-and-normalization.md", "FULL"),
        ("docs/contracts/planning-snapshot.md", "FULL"),
        ("docs/contracts/planning-problem.md", "FULL"),
        ("docs/contracts/planning-policy-and-solve-limits.md", "FULL"),
        ("docs/contracts/execution-events-and-replan-request.md", "FULL"),
        ("docs/contracts/planning-solution-and-schedule-version.md", "FULL"),
        ("docs/adr/ADR-0010-planning-problem-v2-contract-evolution.md", "FULL"),
        ("docs/adr/ADR-0013-execution-event-authority-fact-projection-replan-lineage.md", "FULL"),
        ("docs/adr/ADR-0014-freeze-window-stability-change-report.md", "FULL"),
        ("schemas/json/execution-event.schema.json", "FULL"),
        ("schemas/json/replan-request.schema.json", "FULL"),
        ("schemas/json/schedule-version.v2.schema.json", "FULL"),
        ("schemas/json/change-report.schema.json", "FULL"),
        ("backend/app/domain/execution_contracts.py", "FULL"),
        ("backend/app/domain/execution_fact_projection.py", "FULL"),
        ("backend/app/application/execution_fact_projection.py", "FULL"),
        ("backend/app/application/replan_application.py", "FULL"),
        ("backend/app/importers/urgent_demand.py", "FULL"),
        ("backend/app/planning/problem/freeze_projection.py", "FULL"),
        ("backend/app/planning/reporting/kpi.py", "FULL"),
        ("backend/app/planning/reporting/change_report.py", "FULL"),
        ("backend/app/planning/validation/replan_candidate_validator.py", "FULL"),
        ("backend/app/planning/strategies/lexicographic_replan.py", "FULL"),
        ("backend/app/planning/backends/cp_sat/replan_backend.py", "FULL"),
        ("backend/app/infrastructure/execution_event_repository.py", "FULL"),
        ("backend/app/infrastructure/replan_repository.py", "FULL"),
        ("backend/app/simulation/scenarios/disruption_replay_check.py", "FULL"),
    ),
}


def build_manifest(task_id: str) -> dict[str, object]:
    try:
        selected_inputs = SELECTED_INPUTS_BY_TASK[task_id]
    except KeyError as error:
        raise ValueError(f"unsupported Demo task id: {task_id}") from error
    files: list[dict[str, object]] = []
    total_characters = 0
    for relative_path, load_mode in selected_inputs:
        path = REPOSITORY_ROOT / relative_path
        payload = path.read_bytes()
        text = payload.decode("utf-8")
        total_characters += len(text)
        files.append(
            {
                "path": relative_path,
                "load_mode": load_mode,
                "characters": len(text),
                "sha256": sha256(payload).hexdigest(),
            }
        )
    return {
        "manifest_version": "demo-task-context-manifest.v1",
        "task_id": task_id,
        "task_family": "demo-exclusive",
        "phase_registration": None,
        "diff_base": "fd9ce328a180a8b1f0baa1a0fe870a8d39e0d200",
        "files_allowed_to_change": ["demo/**"],
        "root_repository_consumption": "READ_ONLY",
        "validation_profile": "DEMO_HIGH_RISK",
        "selected_input_count": len(files),
        "estimated_characters": total_characters,
        "soft_budget_note": "Selected normative units were read in full; the 30k character budget is soft.",
        "inputs": files,
        "on_demand_expansion_triggers": [
            "formal contract or accepted ADR conflict",
            "root code/schema change becomes necessary",
            "dynamic replan implementation starts",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument(
        "--task-id",
        choices=tuple(SELECTED_INPUTS_BY_TASK),
        default="TASK-DEMO-01",
    )
    arguments = parser.parse_args()
    report = build_manifest(arguments.task_id)
    arguments.report.parent.mkdir(parents=True, exist_ok=True)
    arguments.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": "PASS", "report": str(arguments.report.resolve()), "inputs": report["selected_input_count"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
