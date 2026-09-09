from __future__ import annotations

import json
from pathlib import Path
import unittest

from aps_extension_sdk import (
    ExtensionInputView,
    ObjectiveContext,
    PlanningRuleContext,
    ReplanAction,
    ReplanContext,
    parse_extension_manifest,
)
from example_beta_extension.objective import BetaPriorityObjective
from example_beta_extension.planning_rule import BetaPriorityRule
from example_beta_extension.replan import BetaReplanPolicy


ROOT = Path(__file__).resolve().parents[1]


class BetaContractTests(unittest.TestCase):
    def setUp(self) -> None:
        document = json.loads(
            (ROOT / "extension/extension-manifest.json").read_text(encoding="utf-8")
        )
        self.manifest = parse_extension_manifest(document)

    def _view(self, contribution_id: str) -> ExtensionInputView:
        return ExtensionInputView.from_json(
            view_contract_version="runtime.extension.input.v1",
            extension_id=self.manifest.extension_id,
            contribution_id=contribution_id,
            input_fingerprint="sha256:" + "b" * 64,
            scope={
                "extension_configuration": {
                    "values": {"replan_event": "synthetic.disruption"}
                }
            },
            facts={
                "operations": [
                    {"operation_id": "operation-b", "enterprise_priority": 1},
                    {"operation_id": "operation-a", "enterprise_priority": 3},
                ],
                "events": ["synthetic.disruption"],
            },
            provenance={"fixture": "synthetic"},
        )

    def test_objective_is_integer_and_replayable(self) -> None:
        descriptor = self.manifest.contributions[1]
        target = BetaPriorityObjective(descriptor)
        context = ObjectiveContext(self._view(descriptor.contribution_id))
        self.assertEqual(target.evaluate(context), target.evaluate(context))
        self.assertEqual(target.evaluate(context).integer_value, 4)

    def test_planning_rule_is_order_stable(self) -> None:
        descriptor = self.manifest.contributions[0]
        target = BetaPriorityRule(descriptor)
        context = PlanningRuleContext(self._view(descriptor.contribution_id))
        self.assertEqual(target.apply(context), target.apply(context))

    def test_replan_echoes_protected_bindings(self) -> None:
        descriptor = self.manifest.contributions[2]
        target = BetaReplanPolicy(descriptor)
        context = ReplanContext(
            input_view=self._view(descriptor.contribution_id),
            execution_fact_fingerprint="sha256:" + "1" * 64,
            hard_lock_fingerprint="sha256:" + "2" * 64,
            freeze_window_fingerprint="sha256:" + "3" * 64,
            state_machine_version="planning.run.state.v1",
            publication_authority_reference="authority.synthetic",
        )
        decision = target.decide(context)
        self.assertIs(decision.action, ReplanAction.REQUEST_REPLAN)
        self.assertEqual(decision.hard_lock_fingerprint, context.hard_lock_fingerprint)


if __name__ == "__main__":
    unittest.main()
