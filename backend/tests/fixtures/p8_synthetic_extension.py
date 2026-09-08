"""Synthetic trusted implementations used only by TASK-P8-13 tests."""

from __future__ import annotations

from dataclasses import replace
from time import sleep
from typing import cast

from aps_extension_sdk import (
    CompatibilityPolicy,
    ConstraintContext,
    ConstraintOutput,
    ContributionManifest,
    ExtensionManifest,
    FrozenJsonObject,
    ObjectiveContext,
    ObjectiveOutput,
    ObjectiveSense,
    ObjectiveStage,
    PlanningRuleContext,
    PlanningRuleOutput,
    RegistryResolution,
    ReplanAction,
    ReplanContext,
    ReplanDecision,
    ValidationContext,
    ValidationOutput,
    fingerprint_json,
    freeze_json,
    resolve_manifest_set,
)


def _frozen(value: object) -> FrozenJsonObject:
    return cast(FrozenJsonObject, freeze_json(value))


class _Implementation:
    def __init__(self, descriptor: ContributionManifest) -> None:
        self._descriptor = descriptor

    @property
    def descriptor(self) -> ContributionManifest:
        return self._descriptor


class SyntheticConstraint(_Implementation):
    def contribute(self, context: ConstraintContext) -> ConstraintOutput:
        return ConstraintOutput(
            contribution_id=self.descriptor.contribution_id,
            constraint_contract_version="com.example.capacity.v1",
            constraint_specification=_frozen(
                {
                    "kind": "synthetic.capacity",
                    "input_fingerprint": context.input_view.input_fingerprint,
                }
            ),
            validation_rule_ids=self.descriptor.validation_rule_ids,
        )


class SyntheticPlanningRule(_Implementation):
    def apply(self, context: PlanningRuleContext) -> PlanningRuleOutput:
        return PlanningRuleOutput(
            contribution_id=self.descriptor.contribution_id,
            output_contract_version="com.example.sequence.v1",
            output=_frozen(
                {
                    "kind": "synthetic.sequence",
                    "input_fingerprint": context.input_view.input_fingerprint,
                }
            ),
            affects_feasibility=self.descriptor.affects_feasibility,
            validation_rule_ids=self.descriptor.validation_rule_ids,
        )


class SyntheticValidationRule(_Implementation):
    def validate(self, context: ValidationContext) -> ValidationOutput:
        del context
        return ValidationOutput(
            contribution_id=self.descriptor.contribution_id,
            validated_contribution_ids=self.descriptor.validates_contribution_ids,
            passed=True,
            violations=(),
        )


class SyntheticObjective(_Implementation):
    def evaluate(self, context: ObjectiveContext) -> ObjectiveOutput:
        return ObjectiveOutput(
            contribution_id=self.descriptor.contribution_id,
            metric_id="com.example.synthetic.cost",
            stage=ObjectiveStage.ENTERPRISE_TIE_BREAK,
            sense=ObjectiveSense.MINIMIZE,
            integer_value=len(context.input_view.facts),
            integer_scale=1,
            authority_reference="authority.synthetic",
            evidence=_frozen(
                {"input_fingerprint": context.input_view.input_fingerprint}
            ),
        )


class SyntheticReplanPolicy(_Implementation):
    def decide(self, context: ReplanContext) -> ReplanDecision:
        return ReplanDecision(
            contribution_id=self.descriptor.contribution_id,
            action=ReplanAction.NO_REPLAN,
            reason_code="com.example.no.replan",
            trigger_references=(),
            execution_fact_fingerprint=context.execution_fact_fingerprint,
            hard_lock_fingerprint=context.hard_lock_fingerprint,
            freeze_window_fingerprint=context.freeze_window_fingerprint,
            state_machine_version=context.state_machine_version,
            publication_authority_reference=(
                context.publication_authority_reference
            ),
        )


class SyntheticRegistry(_Implementation):
    def resolve(
        self,
        manifests: tuple[ExtensionManifest, ...],
        compatibility: CompatibilityPolicy,
    ) -> RegistryResolution:
        return resolve_manifest_set(manifests, compatibility)


class DivergentRegistry(SyntheticRegistry):
    def resolve(
        self,
        manifests: tuple[ExtensionManifest, ...],
        compatibility: CompatibilityPolicy,
    ) -> RegistryResolution:
        resolved = super().resolve(manifests, compatibility)
        return replace(
            resolved,
            resolution_fingerprint=fingerprint_json(
                {"forged": resolved.resolution_fingerprint}
            ),
        )


class CrashingObjective(SyntheticObjective):
    def evaluate(self, context: ObjectiveContext) -> ObjectiveOutput:
        del context
        raise RuntimeError("customer-secret=do-not-leak")


class SlowObjective(SyntheticObjective):
    def evaluate(self, context: ObjectiveContext) -> ObjectiveOutput:
        sleep(0.1)
        return super().evaluate(context)


class ForgedObjective(SyntheticObjective):
    def evaluate(self, context: ObjectiveContext) -> ObjectiveOutput:
        return replace(
            super().evaluate(context),
            contribution_id="com.example.forged.objective",
        )


__all__ = [
    "CrashingObjective",
    "DivergentRegistry",
    "ForgedObjective",
    "SlowObjective",
    "SyntheticConstraint",
    "SyntheticObjective",
    "SyntheticPlanningRule",
    "SyntheticRegistry",
    "SyntheticReplanPolicy",
    "SyntheticValidationRule",
]
