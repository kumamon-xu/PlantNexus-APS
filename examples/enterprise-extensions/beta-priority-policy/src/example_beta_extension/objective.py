"""Integer-only objective in the enterprise tie-break stage."""

from __future__ import annotations

from aps_extension_sdk import (
    ContributionManifest,
    FrozenJsonObject,
    ObjectiveContext,
    ObjectiveOutput,
    ObjectiveSense,
    ObjectiveStage,
    freeze_json,
)


class BetaPriorityObjective:
    def __init__(self, descriptor: ContributionManifest) -> None:
        self._descriptor = descriptor

    @property
    def descriptor(self) -> ContributionManifest:
        return self._descriptor

    def evaluate(self, context: ObjectiveContext) -> ObjectiveOutput:
        total = 0
        operations = context.input_view.facts.get("operations", ())
        if isinstance(operations, tuple):
            for operation in operations:
                if isinstance(operation, FrozenJsonObject):
                    priority = operation.get("enterprise_priority", 0)
                    if isinstance(priority, int) and not isinstance(priority, bool):
                        total += priority
        evidence = freeze_json(
            {
                "input_fingerprint": context.input_view.input_fingerprint,
                "metric_kind": "synthetic.beta.priority_total",
            }
        )
        assert isinstance(evidence, FrozenJsonObject)
        return ObjectiveOutput(
            contribution_id=self.descriptor.contribution_id,
            metric_id="synthetic.beta.priority_total",
            stage=ObjectiveStage.ENTERPRISE_TIE_BREAK,
            sense=ObjectiveSense.MAXIMIZE,
            integer_value=total,
            integer_scale=1,
            authority_reference="com.example.aps.beta.priority.authority",
            evidence=evidence,
        )


__all__ = ["BetaPriorityObjective"]
