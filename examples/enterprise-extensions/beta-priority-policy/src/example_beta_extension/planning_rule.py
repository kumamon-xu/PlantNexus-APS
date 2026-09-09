"""Deterministic non-feasibility planning order hint."""

from __future__ import annotations

from aps_extension_sdk import (
    ContributionManifest,
    FrozenJsonObject,
    PlanningRuleContext,
    PlanningRuleOutput,
    freeze_json,
)


class BetaPriorityRule:
    def __init__(self, descriptor: ContributionManifest) -> None:
        self._descriptor = descriptor

    @property
    def descriptor(self) -> ContributionManifest:
        return self._descriptor

    def apply(self, context: PlanningRuleContext) -> PlanningRuleOutput:
        rows: list[tuple[int, str]] = []
        operations = context.input_view.facts.get("operations", ())
        if isinstance(operations, tuple):
            for operation in operations:
                if isinstance(operation, FrozenJsonObject):
                    operation_id = operation.get("operation_id")
                    priority = operation.get("enterprise_priority", 0)
                    if (
                        isinstance(operation_id, str)
                        and isinstance(priority, int)
                        and not isinstance(priority, bool)
                    ):
                        rows.append((-priority, operation_id))
        output = freeze_json(
            {
                "kind": "synthetic.beta.priority_order",
                "ordered_operation_ids": [
                    operation_id for _, operation_id in sorted(rows)
                ],
            }
        )
        assert isinstance(output, FrozenJsonObject)
        return PlanningRuleOutput(
            contribution_id=self.descriptor.contribution_id,
            output_contract_version="synthetic.beta.priority_order.v1",
            output=output,
            affects_feasibility=False,
            validation_rule_ids=(),
        )


__all__ = ["BetaPriorityRule"]
