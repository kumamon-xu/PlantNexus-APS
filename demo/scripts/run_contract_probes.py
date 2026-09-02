"""Emit executable compatibility probes for known Demo integration boundaries."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import fields
import inspect
import json
from pathlib import Path
import sys

from jsonschema import Draft202012Validator


DEMO_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = DEMO_ROOT.parent
sys.path.insert(0, str(REPOSITORY_ROOT / "backend"))
sys.path.insert(0, str(DEMO_ROOT / "backend"))

from app.application.replan_application import ReplanApplicationInput  # noqa: E402
from app.domain.workspace_contracts import (  # noqa: E402
    WorkspaceContractError,
    require_workspace_document,
)
from app.planning.validation.replan_candidate_validator import (  # noqa: E402
    validate_replan_candidate,
)
from app.simulation.scenarios import disruption_replay_check  # noqa: E402
from plantnexus_demo import DemoIngressPipeline, DemoPackageGenerator  # noqa: E402


def _probe(name: str, check: bool, evidence: dict[str, object]) -> dict[str, object]:
    return {"probe_id": name, "status": "PASS" if check else "FAIL", "evidence": evidence}


def run_probes() -> dict[str, object]:
    generated = DemoPackageGenerator().prepare_batch("smoke")
    artifacts = DemoIngressPipeline().run(generated)
    problem = artifacts.problem.document

    workspace_rejected = False
    workspace_error = ""
    try:
        require_workspace_document(problem)
    except WorkspaceContractError as error:
        workspace_rejected = True
        workspace_error = str(error)

    schema = json.loads(
        (REPOSITORY_ROOT / "schemas/json/execution-event.schema.json").read_text(
            encoding="utf-8"
        )
    )
    sample = json.loads(
        (REPOSITORY_ROOT / "schemas/samples/execution-event.v1.synthetic.json").read_text(
            encoding="utf-8"
        )
    )
    sample["event_type"] = "URGENT_DEMAND_RECEIVED"
    sample["entity_refs"] = [
        {"entity_type": "DEMAND_ORDER", "entity_id": "demand-order-demo-urgent-001"}
    ]
    sample["payload"] = {
        "kind": "URGENT_DEMAND_RECEIVED",
        "demand_order_id": "demand-order-demo-urgent-001",
        "quantity": 3,
        "due_at_utc": "2026-09-09T06:00:00Z",
        "priority_weight": 12,
        "priority_source": {
            "source_system": "plantnexus-synthetic-policy",
            "source_version": "1.0.0",
            "source_record_id": "priority-demo-urgent-001",
        },
    }
    validator = Draft202012Validator(schema)
    base_event_errors = list(validator.iter_errors(sample))
    event_with_route = deepcopy(sample)
    event_with_route["payload"]["route_template_id"] = "CNC-ROUTE-4"
    route_errors = list(validator.iter_errors(event_with_route))

    replan_source = inspect.getsource(validate_replan_candidate)
    added_operation_contract = (
        'projection.get("added_operation_ids")' in replan_source
        and 'sorted(set(active_ids) - set(base))' in replan_source
        and 'classifications[operation_id] = "ADDED"' in replan_source
    )
    replan_input_fields = {field.name for field in fields(ReplanApplicationInput)}
    kpi_capture_available = (
        {"before_kpi", "after_kpi"}.issubset(replan_input_fields)
        and hasattr(disruption_replay_check, "_KpiCapturingStrategy")
    )
    template_lengths = {
        len(template["steps"])
        for template in DemoPackageGenerator().assets.route_templates["templates"]
    }

    probes = [
        _probe(
            "DEMO-CONTRACT-001",
            workspace_rejected,
            {
                "boundary": "P3 workspace carrier remains v1-only",
                "problem_version": problem["problem_version"],
                "rejection": workspace_error,
                "implementation_implication": "Demo needs an adapter/read model before reusing the P3 workspace UI.",
            },
        ),
        _probe(
            "DEMO-CONTRACT-002",
            not base_event_errors and bool(route_errors),
            {
                "urgent_event_without_route_errors": len(base_event_errors),
                "urgent_event_with_route_template_errors": len(route_errors),
                "implementation_implication": "route_template_id stays in the Demo command/import layer, not ExecutionEvent payload.",
            },
        ),
        _probe(
            "DEMO-CONTRACT-003",
            added_operation_contract,
            {
                "validator_function": "validate_replan_candidate",
                "added_operation_universe": "active_ids - base_ids",
                "change_classification": "ADDED",
                "implementation_implication": "Urgent routing additions can be represented after Standard Import and projection.",
            },
        ),
        _probe(
            "DEMO-CONTRACT-004",
            kpi_capture_available,
            {
                "replan_input_fields": sorted(replan_input_fields),
                "existing_kpi_capture_adapter": kpi_capture_available,
                "implementation_implication": "Demo orchestration must calculate and inject real before/after KPI documents.",
            },
        ),
        _probe(
            "DEMO-CONTRACT-005",
            artifacts.quality.passed and template_lengths == {3, 4, 5, 6},
            {
                "route_template_lengths": sorted(template_lengths),
                "standard_import_quality": artifacts.quality.document["status"],
                "problem_version": problem["problem_version"],
                "problem_hash": artifacts.problem.problem_hash,
            },
        ),
    ]
    return {
        "contract_probe_report_version": "cnc-demo-contract-probes.v1",
        "status": "PASS" if all(item["status"] == "PASS" for item in probes) else "FAIL",
        "task_id": "TASK-DEMO-01",
        "demo_exclusive": True,
        "probe_count": len(probes),
        "probes": probes,
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    arguments = parser.parse_args()
    report = run_probes()
    arguments.report.parent.mkdir(parents=True, exist_ok=True)
    arguments.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": report["status"], "report": str(arguments.report.resolve())}, ensure_ascii=False))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
