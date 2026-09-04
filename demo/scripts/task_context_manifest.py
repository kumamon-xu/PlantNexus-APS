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
    "TASK-DEMO-04": (
        ("demo/docs/TASK-DEMO-04-unified-presentation-and-read-api.md", "FULL"),
        ("demo/docs/03-architecture-and-api.md", "SECTIONS_9_10"),
        ("demo/docs/05-benchmark-and-acceptance.md", "B5_AND_GATE_E"),
        ("demo/docs/TASKS.md", "D11_AND_D12"),
        ("docs/contracts/planning-workspace-api.md", "FULL"),
        ("docs/contracts/planning-solution-and-schedule-version.md", "FULL"),
        ("docs/adr/ADR-0008-utc-seconds-and-solver-ticks.md", "FULL"),
        ("docs/adr/ADR-0010-planning-problem-v2-contract-evolution.md", "FULL"),
        ("docs/adr/ADR-0014-freeze-window-stability-change-report.md", "FULL"),
        ("schemas/json/schedule-version.schema.json", "FULL"),
        ("schemas/json/schedule-version.v2.schema.json", "FULL"),
        ("schemas/json/solver-report.schema.json", "FULL"),
        ("schemas/json/solver-report.v2.schema.json", "FULL"),
        ("schemas/json/validation-report.schema.json", "FULL"),
        ("schemas/json/validation-report.v2.schema.json", "FULL"),
        ("schemas/json/kpi.schema.json", "FULL"),
        ("schemas/json/kpi.v2.schema.json", "FULL"),
        ("schemas/json/change-report.schema.json", "FULL"),
        ("backend/app/domain/workspace_contracts.py", "RELEVANT_SYMBOLS"),
        ("backend/app/application/workspace_queries.py", "RELEVANT_SYMBOLS"),
        ("backend/app/application/change_report_queries.py", "FULL"),
        ("backend/app/infrastructure/workspace_persistence.py", "RELEVANT_SYMBOLS"),
        ("demo/backend/plantnexus_demo/persistence.py", "RELEVANT_SYMBOLS"),
        ("demo/backend/plantnexus_demo/composition.py", "RELEVANT_SYMBOLS"),
        ("demo/backend/plantnexus_demo/api.py", "FULL"),
    ),
    "TASK-DEMO-05": (
        ("demo/docs/TASK-DEMO-05-chinese-story-shell-and-job-recovery.md", "FULL"),
        ("demo/docs/04-ux-and-demo-script.md", "SECTIONS_1_2_5_7_9_10"),
        ("demo/docs/03-architecture-and-api.md", "SECTIONS_6_10_11"),
        ("demo/docs/05-benchmark-and-acceptance.md", "GATES_E_F"),
        ("demo/docs/TASKS.md", "D13"),
        ("demo/docs/TASK-DEMO-04-unified-presentation-and-read-api.md", "COMPLETION_SUMMARY"),
        ("demo/backend/plantnexus_demo/api.py", "FULL"),
        ("demo/backend/plantnexus_demo/composition.py", "STORY_STATE"),
        ("demo/backend/plantnexus_demo/jobs.py", "FULL"),
        ("demo/backend/plantnexus_demo/presentation.py", "RESPONSE_CONTRACTS"),
        ("demo/backend/plantnexus_demo/security.py", "FULL"),
        ("frontend/package.json", "FULL"),
        ("frontend/vite.config.ts", "FULL"),
        ("frontend/tsconfig.app.json", "FULL"),
        ("frontend/src/main.tsx", "TECHNICAL_BASELINE"),
        ("frontend/src/styles/app.css", "RESPONSIVE_BASELINE"),
        ("frontend/tests/setup.ts", "TEST_BASELINE"),
    ),
    "TASK-DEMO-06": (
        ("demo/docs/TASK-DEMO-06-schedule-workspace-and-capacity-view.md", "FULL"),
        ("demo/docs/04-ux-and-demo-script.md", "SECTIONS_2_3_4_5_7"),
        ("demo/docs/05-benchmark-and-acceptance.md", "SECTIONS_5_6_GATE_E_10"),
        ("demo/docs/TASKS.md", "D14"),
        ("demo/docs/TASK-DEMO-04-unified-presentation-and-read-api.md", "PRESENTATION_CONTRACT"),
        ("demo/docs/TASK-DEMO-05-chinese-story-shell-and-job-recovery.md", "COMPLETION_SUMMARY"),
        ("demo/backend/plantnexus_demo/presentation.py", "RESPONSE_CONTRACTS"),
        ("demo/backend/plantnexus_demo/api.py", "PRESENTATION_GET_ENDPOINTS"),
        ("demo/frontend/src/api/types.ts", "FULL"),
        ("demo/frontend/src/api/contracts.ts", "FULL"),
        ("demo/frontend/src/api/client.ts", "FULL"),
        ("demo/frontend/src/app/useDemoStory.ts", "FULL"),
        ("demo/frontend/src/DemoApp.tsx", "FULL"),
        ("demo/frontend/src/domain/copy.ts", "FULL"),
        ("demo/frontend/src/styles/demo.css", "FULL"),
        ("demo/frontend/tests/fixtures.ts", "FULL"),
        ("demo/frontend/tests/DemoApp.test.tsx", "FULL"),
    ),
    "TASK-DEMO-07": (
        ("demo/docs/TASK-DEMO-07-urgent-replan-and-comparison-workspace.md", "FULL"),
        ("demo/docs/02-cnc-data-design.md", "SECTION_4"),
        ("demo/docs/03-architecture-and-api.md", "SECTIONS_8_9_10"),
        ("demo/docs/04-ux-and-demo-script.md", "SECTIONS_2_4_2_5_3_TO_8_10"),
        ("demo/docs/05-benchmark-and-acceptance.md", "B4_B5_GATES_D_E_F_TEST_MATRIX"),
        ("demo/docs/TASKS.md", "D15"),
        ("demo/docs/TASK-DEMO-03-urgent-order-and-dynamic-replan.md", "COMPLETION_SUMMARY"),
        ("demo/docs/TASK-DEMO-04-unified-presentation-and-read-api.md", "COMPARISON_CONTRACT"),
        ("demo/docs/TASK-DEMO-06-schedule-workspace-and-capacity-view.md", "COMPLETION_SUMMARY"),
        ("demo/data/cnc-showcase/route-templates.json", "FULL"),
        ("demo/data/cnc-showcase/priority-policy.json", "FULL"),
        ("demo/backend/plantnexus_demo/orchestration.py", "URGENT_COMMAND_AND_JOB"),
        ("demo/backend/plantnexus_demo/presentation.py", "COMPARISON_RESPONSE_CONTRACT"),
        ("demo/backend/plantnexus_demo/api.py", "URGENT_AND_COMPARISON_ENDPOINTS"),
        ("demo/frontend/src/api/types.ts", "FULL"),
        ("demo/frontend/src/api/contracts.ts", "FULL"),
        ("demo/frontend/src/api/client.ts", "FULL"),
        ("demo/frontend/src/app/commandIdentity.ts", "FULL"),
        ("demo/frontend/src/app/useDemoStory.ts", "FULL"),
        ("demo/frontend/src/DemoApp.tsx", "FULL"),
        ("demo/frontend/src/components/JobPanel.tsx", "FULL"),
        ("demo/frontend/src/styles/demo.css", "FULL"),
        ("demo/frontend/tests/fixtures.ts", "FULL"),
        ("demo/frontend/tests/DemoApp.test.tsx", "FULL"),
    ),
    "TASK-DEMO-08": (
        ("demo/docs/TASK-DEMO-08-e2e-security-recovery-and-accessibility.md", "FULL"),
        ("demo/docs/03-architecture-and-api.md", "SECURITY_AND_RECOVERY"),
        ("demo/docs/04-ux-and-demo-script.md", "E2E_FAILURE_AND_ACCESSIBILITY"),
        ("demo/docs/05-benchmark-and-acceptance.md", "GATES_E_F_AND_TEST_MATRIX"),
        ("demo/docs/TASKS.md", "D16"),
        ("demo/docs/TASK-DEMO-05-chinese-story-shell-and-job-recovery.md", "COMPLETION_SUMMARY"),
        ("demo/docs/TASK-DEMO-06-schedule-workspace-and-capacity-view.md", "COMPLETION_SUMMARY"),
        ("demo/docs/TASK-DEMO-07-urgent-replan-and-comparison-workspace.md", "COMPLETION_SUMMARY"),
        ("docs/contracts/authorization-and-audit.md", "FULL"),
        ("demo/backend/plantnexus_demo/api.py", "SECURITY_AND_COMMAND_ENDPOINTS"),
        ("demo/backend/plantnexus_demo/composition.py", "RUNTIME_COMPOSITION"),
        ("demo/backend/plantnexus_demo/jobs.py", "RECOVERY_AND_MUTEX"),
        ("demo/backend/plantnexus_demo/persistence.py", "PATH_JOB_AND_CAS"),
        ("demo/backend/plantnexus_demo/security.py", "FULL"),
        ("demo/scripts/start_demo.py", "FULL"),
        ("demo/scripts/validate_demo.py", "FULL"),
        ("demo/frontend/src/DemoApp.tsx", "FULL"),
        ("demo/frontend/src/app/useDemoStory.ts", "FULL"),
        ("demo/frontend/src/components/ConfirmationDialog.tsx", "FULL"),
        ("demo/frontend/src/components/UrgentOrderPanel.tsx", "FULL"),
        ("demo/frontend/src/components/ComparisonWorkspace.tsx", "FULL"),
        ("demo/frontend/src/domain/copy.ts", "FULL"),
        ("demo/frontend/src/styles/demo.css", "ACCESSIBILITY_AND_RESPONSIVE"),
        ("demo/frontend/tests/DemoApp.test.tsx", "FULL"),
    ),
}

DIFF_BASE_BY_TASK = {
    "TASK-DEMO-01": "fd9ce328a180a8b1f0baa1a0fe870a8d39e0d200",
    "TASK-DEMO-02": "fd9ce328a180a8b1f0baa1a0fe870a8d39e0d200",
    "TASK-DEMO-03": "fd9ce328a180a8b1f0baa1a0fe870a8d39e0d200",
    "TASK-DEMO-04": "b0cc126522e3916d72b438e7f237851a36b51a3d",
    "TASK-DEMO-05": "b0cc126522e3916d72b438e7f237851a36b51a3d",
    "TASK-DEMO-06": "b0cc126522e3916d72b438e7f237851a36b51a3d",
    "TASK-DEMO-07": "b0cc126522e3916d72b438e7f237851a36b51a3d",
    "TASK-DEMO-08": "9a8f2e556b4b0adfdef3f88e1d442f805e9d4628",
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
        "diff_base": DIFF_BASE_BY_TASK[task_id],
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
            "presentation lineage or fingerprint mismatch cannot be resolved read-only",
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
