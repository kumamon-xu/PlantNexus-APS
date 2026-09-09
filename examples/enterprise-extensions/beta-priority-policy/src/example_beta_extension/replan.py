"""Replan request policy that preserves all Runtime authority bindings."""

from __future__ import annotations

from collections.abc import Mapping

from aps_extension_sdk import (
    ContributionManifest,
    ReplanAction,
    ReplanContext,
    ReplanDecision,
)


class BetaReplanPolicy:
    def __init__(self, descriptor: ContributionManifest) -> None:
        self._descriptor = descriptor

    @property
    def descriptor(self) -> ContributionManifest:
        return self._descriptor

    def decide(self, context: ReplanContext) -> ReplanDecision:
        configuration = context.input_view.scope.get("extension_configuration")
        values = (
            configuration.get("values") if isinstance(configuration, Mapping) else None
        )
        configured = values.get("replan_event") if isinstance(values, Mapping) else None
        replan_event = (
            configured if isinstance(configured, str) else "synthetic.disruption"
        )
        events = context.input_view.facts.get("events", ())
        triggers = (
            tuple(
                sorted(
                    value
                    for value in events
                    if isinstance(value, str) and value == replan_event
                )
            )
            if isinstance(events, tuple)
            else ()
        )
        return ReplanDecision(
            contribution_id=self.descriptor.contribution_id,
            action=ReplanAction.REQUEST_REPLAN if triggers else ReplanAction.NO_REPLAN,
            reason_code="synthetic.beta.disruption"
            if triggers
            else "synthetic.beta.no_disruption",
            trigger_references=triggers,
            execution_fact_fingerprint=context.execution_fact_fingerprint,
            hard_lock_fingerprint=context.hard_lock_fingerprint,
            freeze_window_fingerprint=context.freeze_window_fingerprint,
            state_machine_version=context.state_machine_version,
            publication_authority_reference=context.publication_authority_reference,
        )


__all__ = ["BetaReplanPolicy"]
