from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any, cast

import pytest
from jsonschema import Draft202012Validator

from app.domain.workspace_contracts import WorkspaceContractError, require_workspace_document
from plantnexus_demo import DemoIngressPipeline, DemoPackageGenerator


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _urgent_event() -> dict[str, object]:
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
    return sample


def test_execution_event_contract_keeps_route_template_outside_event_payload() -> None:
    schema = json.loads(
        (REPOSITORY_ROOT / "schemas/json/execution-event.schema.json").read_text(
            encoding="utf-8"
        )
    )
    validator = Draft202012Validator(schema)
    event = _urgent_event()
    validator.validate(event)

    with_route = deepcopy(event)
    with_route["payload"]["route_template_id"] = "CNC-ROUTE-4"  # type: ignore[index]
    errors = list(validator.iter_errors(cast(Any, with_route)))
    assert errors
    assert any("Additional properties are not allowed" in error.message for error in errors)


def test_v1_workspace_carrier_does_not_accept_a_v2_planning_problem() -> None:
    problem = DemoIngressPipeline().run(
        DemoPackageGenerator().prepare_batch("smoke")
    ).problem.document
    with pytest.raises(WorkspaceContractError, match="supported workspace document version"):
        require_workspace_document(problem)
