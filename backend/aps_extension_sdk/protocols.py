"""Public APS Extension SDK v1 protocols and immutable input/output values."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, runtime_checkable

from aps_extension_sdk.errors import ExtensionErrorCode, fail
from aps_extension_sdk.manifest import (
    CompatibilityPolicy,
    ContributionManifest,
    ExtensionManifest,
    ExtensionPoint,
    ObjectiveStage,
    RegistryResolution,
)
from aps_extension_sdk.values import (
    FrozenJsonObject,
    assert_immutable_json,
    freeze_json,
    require_fingerprint,
    require_identifier,
)


class ObjectiveSense(StrEnum):
    MINIMIZE = "MINIMIZE"
    MAXIMIZE = "MAXIMIZE"


class ReplanAction(StrEnum):
    NO_REPLAN = "NO_REPLAN"
    REQUEST_REPLAN = "REQUEST_REPLAN"


def _require_frozen_object(value: object, *, field: str) -> FrozenJsonObject:
    if not isinstance(value, FrozenJsonObject):
        fail(
            ExtensionErrorCode.MUTABLE_VALUE,
            field,
            "value must be a FrozenJsonObject",
        )
    assert_immutable_json(value, field=field)
    return value


def _require_ordered_ids(values: tuple[str, ...], *, field: str) -> None:
    if values != tuple(sorted(values)) or len(values) != len(set(values)):
        fail(
            ExtensionErrorCode.INVALID_MANIFEST,
            field,
            "IDs must be unique and canonically sorted",
        )
    for value in values:
        require_identifier(value, field=field)


@dataclass(frozen=True, slots=True)
class ExtensionInputView:
    """Runtime-cropped, authority-neutral input copied across the SDK boundary."""

    view_contract_version: str
    extension_id: str
    contribution_id: str
    input_fingerprint: str
    scope: FrozenJsonObject
    facts: FrozenJsonObject
    provenance: FrozenJsonObject

    def __post_init__(self) -> None:
        require_identifier(self.view_contract_version, field="view_contract_version")
        require_identifier(self.extension_id, field="extension_id")
        require_identifier(self.contribution_id, field="contribution_id")
        require_fingerprint(self.input_fingerprint, field="input_fingerprint")
        for field, value in (
            ("scope", self.scope),
            ("facts", self.facts),
            ("provenance", self.provenance),
        ):
            _require_frozen_object(value, field=field)

    @classmethod
    def from_json(
        cls,
        *,
        view_contract_version: str,
        extension_id: str,
        contribution_id: str,
        input_fingerprint: str,
        scope: object,
        facts: object,
        provenance: object,
    ) -> ExtensionInputView:
        frozen_scope = freeze_json(scope, field="scope")
        frozen_facts = freeze_json(facts, field="facts")
        frozen_provenance = freeze_json(provenance, field="provenance")
        if not isinstance(frozen_scope, FrozenJsonObject):
            fail(
                ExtensionErrorCode.MUTABLE_VALUE,
                "scope",
                "scope must be a JSON object",
            )
        if not isinstance(frozen_facts, FrozenJsonObject):
            fail(
                ExtensionErrorCode.MUTABLE_VALUE,
                "facts",
                "facts must be a JSON object",
            )
        if not isinstance(frozen_provenance, FrozenJsonObject):
            fail(
                ExtensionErrorCode.MUTABLE_VALUE,
                "provenance",
                "provenance must be a JSON object",
            )
        return cls(
            view_contract_version=view_contract_version,
            extension_id=extension_id,
            contribution_id=contribution_id,
            input_fingerprint=input_fingerprint,
            scope=frozen_scope,
            facts=frozen_facts,
            provenance=frozen_provenance,
        )


@dataclass(frozen=True, slots=True)
class ConstraintContext:
    input_view: ExtensionInputView


@dataclass(frozen=True, slots=True)
class ObjectiveContext:
    input_view: ExtensionInputView


@dataclass(frozen=True, slots=True)
class PlanningRuleContext:
    input_view: ExtensionInputView


@dataclass(frozen=True, slots=True)
class ValidationContext:
    input_view: ExtensionInputView


@dataclass(frozen=True, slots=True)
class ReplanContext:
    input_view: ExtensionInputView
    execution_fact_fingerprint: str
    hard_lock_fingerprint: str
    freeze_window_fingerprint: str
    state_machine_version: str
    publication_authority_reference: str

    def __post_init__(self) -> None:
        require_fingerprint(
            self.execution_fact_fingerprint,
            field="execution_fact_fingerprint",
        )
        require_fingerprint(self.hard_lock_fingerprint, field="hard_lock_fingerprint")
        require_fingerprint(
            self.freeze_window_fingerprint,
            field="freeze_window_fingerprint",
        )
        require_identifier(self.state_machine_version, field="state_machine_version")
        require_identifier(
            self.publication_authority_reference,
            field="publication_authority_reference",
        )


@dataclass(frozen=True, slots=True)
class ConstraintOutput:
    contribution_id: str
    constraint_contract_version: str
    constraint_specification: FrozenJsonObject
    validation_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        require_identifier(self.contribution_id, field="contribution_id")
        require_identifier(
            self.constraint_contract_version,
            field="constraint_contract_version",
        )
        if not self.validation_rule_ids:
            fail(
                ExtensionErrorCode.MISSING_VALIDATION_PAIR,
                "validation_rule_ids",
                "Constraint output must name an independent Validation Rule",
            )
        _require_ordered_ids(self.validation_rule_ids, field="validation_rule_ids")
        _require_frozen_object(
            self.constraint_specification,
            field="constraint_specification",
        )


@dataclass(frozen=True, slots=True)
class ObjectiveOutput:
    contribution_id: str
    metric_id: str
    stage: ObjectiveStage
    sense: ObjectiveSense
    integer_value: int
    integer_scale: int
    authority_reference: str
    evidence: FrozenJsonObject

    def __post_init__(self) -> None:
        require_identifier(self.contribution_id, field="contribution_id")
        require_identifier(self.metric_id, field="metric_id")
        require_identifier(self.authority_reference, field="authority_reference")
        if self.stage is not ObjectiveStage.ENTERPRISE_TIE_BREAK:
            fail(
                ExtensionErrorCode.INVALID_OBJECTIVE_STAGE,
                "stage",
                "Objective may only use the enterprise tie-break stage",
            )
        if not isinstance(self.sense, ObjectiveSense):
            fail(
                ExtensionErrorCode.INVALID_OBJECTIVE_STAGE,
                "sense",
                "Objective sense must be a closed SDK enum value",
            )
        if isinstance(self.integer_value, bool) or not isinstance(
            self.integer_value, int
        ):
            fail(
                ExtensionErrorCode.INVALID_OBJECTIVE_STAGE,
                "integer_value",
                "Objective values must be deterministic integers",
            )
        if isinstance(self.integer_scale, bool) or not isinstance(
            self.integer_scale, int
        ) or self.integer_scale <= 0:
            fail(
                ExtensionErrorCode.INVALID_OBJECTIVE_STAGE,
                "integer_scale",
                "Objective scale must be an explicit positive integer",
            )
        _require_frozen_object(self.evidence, field="evidence")


@dataclass(frozen=True, slots=True)
class PlanningRuleOutput:
    contribution_id: str
    output_contract_version: str
    output: FrozenJsonObject
    affects_feasibility: bool
    validation_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        require_identifier(self.contribution_id, field="contribution_id")
        require_identifier(
            self.output_contract_version,
            field="output_contract_version",
        )
        if not isinstance(self.affects_feasibility, bool):
            fail(
                ExtensionErrorCode.INVALID_VALIDATION_PAIR,
                "affects_feasibility",
                "feasibility marker must be boolean",
            )
        if self.affects_feasibility != bool(self.validation_rule_ids):
            fail(
                ExtensionErrorCode.INVALID_VALIDATION_PAIR,
                "validation_rule_ids",
                "feasibility-affecting Planning Rule output needs a validator pair",
            )
        _require_ordered_ids(self.validation_rule_ids, field="validation_rule_ids")
        _require_frozen_object(self.output, field="output")


@dataclass(frozen=True, slots=True)
class ValidationViolation:
    violation_code: str
    entity_ids: tuple[str, ...]
    path: str
    observed: FrozenJsonObject
    expected: FrozenJsonObject
    message_key: str

    def __post_init__(self) -> None:
        require_identifier(self.violation_code, field="violation_code")
        require_identifier(self.message_key, field="message_key")
        if not self.path.startswith("$"):
            fail(
                ExtensionErrorCode.INVALID_MANIFEST,
                "path",
                "violation path must be a stable JSON path",
            )
        _require_ordered_ids(self.entity_ids, field="entity_ids")
        _require_frozen_object(self.observed, field="observed")
        _require_frozen_object(self.expected, field="expected")


@dataclass(frozen=True, slots=True)
class ValidationOutput:
    contribution_id: str
    validated_contribution_ids: tuple[str, ...]
    passed: bool
    violations: tuple[ValidationViolation, ...]

    def __post_init__(self) -> None:
        require_identifier(self.contribution_id, field="contribution_id")
        if not self.validated_contribution_ids:
            fail(
                ExtensionErrorCode.INVALID_VALIDATION_PAIR,
                "validated_contribution_ids",
                "Validation Rule must identify what it independently checked",
            )
        _require_ordered_ids(
            self.validated_contribution_ids,
            field="validated_contribution_ids",
        )
        if not isinstance(self.passed, bool):
            fail(
                ExtensionErrorCode.INVALID_VALIDATION_PAIR,
                "passed",
                "validation result must use a boolean passed marker",
            )
        if self.passed == bool(self.violations):
            fail(
                ExtensionErrorCode.INVALID_VALIDATION_PAIR,
                "violations",
                "PASS requires no violations and FAIL requires at least one",
            )


@dataclass(frozen=True, slots=True)
class ReplanDecision:
    contribution_id: str
    action: ReplanAction
    reason_code: str
    trigger_references: tuple[str, ...]
    execution_fact_fingerprint: str
    hard_lock_fingerprint: str
    freeze_window_fingerprint: str
    state_machine_version: str
    publication_authority_reference: str

    def __post_init__(self) -> None:
        require_identifier(self.contribution_id, field="contribution_id")
        if not isinstance(self.action, ReplanAction):
            fail(
                ExtensionErrorCode.FORBIDDEN_BOUNDARY_ACCESS,
                "action",
                "Replan action must be a closed SDK enum value",
            )
        require_identifier(self.reason_code, field="reason_code")
        _require_ordered_ids(self.trigger_references, field="trigger_references")
        require_fingerprint(
            self.execution_fact_fingerprint,
            field="execution_fact_fingerprint",
        )
        require_fingerprint(self.hard_lock_fingerprint, field="hard_lock_fingerprint")
        require_fingerprint(
            self.freeze_window_fingerprint,
            field="freeze_window_fingerprint",
        )
        require_identifier(self.state_machine_version, field="state_machine_version")
        require_identifier(
            self.publication_authority_reference,
            field="publication_authority_reference",
        )


@runtime_checkable
class Constraint(Protocol):
    @property
    def descriptor(self) -> ContributionManifest: ...

    def contribute(self, context: ConstraintContext) -> ConstraintOutput: ...


@runtime_checkable
class Objective(Protocol):
    @property
    def descriptor(self) -> ContributionManifest: ...

    def evaluate(self, context: ObjectiveContext) -> ObjectiveOutput: ...


@runtime_checkable
class PlanningRule(Protocol):
    @property
    def descriptor(self) -> ContributionManifest: ...

    def apply(self, context: PlanningRuleContext) -> PlanningRuleOutput: ...


@runtime_checkable
class ValidationRule(Protocol):
    @property
    def descriptor(self) -> ContributionManifest: ...

    def validate(self, context: ValidationContext) -> ValidationOutput: ...


@runtime_checkable
class ReplanPolicy(Protocol):
    @property
    def descriptor(self) -> ContributionManifest: ...

    def decide(self, context: ReplanContext) -> ReplanDecision: ...


@runtime_checkable
class PluginRegistry(Protocol):
    @property
    def descriptor(self) -> ContributionManifest: ...

    def resolve(
        self,
        manifests: tuple[ExtensionManifest, ...],
        compatibility: CompatibilityPolicy,
    ) -> RegistryResolution: ...


def validate_protocol_output(
    descriptor: ContributionManifest,
    context: object,
    output: object,
) -> None:
    """Fail closed when an implementation returns the wrong or forged value."""

    if descriptor.extension_point is ExtensionPoint.CONSTRAINT:
        if not isinstance(context, ConstraintContext) or not isinstance(
            output, ConstraintOutput
        ):
            fail(
                ExtensionErrorCode.MUTABLE_VALUE,
                descriptor.contribution_id,
                "Constraint must return ConstraintOutput for ConstraintContext",
            )
        if (
            output.contribution_id != descriptor.contribution_id
            or output.validation_rule_ids != descriptor.validation_rule_ids
        ):
            fail(
                ExtensionErrorCode.INVALID_VALIDATION_PAIR,
                descriptor.contribution_id,
                "Constraint output identity or validator pair differs from manifest",
            )
        return
    if descriptor.extension_point is ExtensionPoint.OBJECTIVE:
        if not isinstance(context, ObjectiveContext) or not isinstance(
            output, ObjectiveOutput
        ):
            fail(
                ExtensionErrorCode.MUTABLE_VALUE,
                descriptor.contribution_id,
                "Objective must return ObjectiveOutput for ObjectiveContext",
            )
        if (
            output.contribution_id != descriptor.contribution_id
            or output.stage is not descriptor.objective_stage
        ):
            fail(
                ExtensionErrorCode.INVALID_OBJECTIVE_STAGE,
                descriptor.contribution_id,
                "Objective output differs from the manifest identity or stage",
            )
        return
    if descriptor.extension_point is ExtensionPoint.PLANNING_RULE:
        if not isinstance(context, PlanningRuleContext) or not isinstance(
            output, PlanningRuleOutput
        ):
            fail(
                ExtensionErrorCode.MUTABLE_VALUE,
                descriptor.contribution_id,
                "Planning Rule must return PlanningRuleOutput for its context",
            )
        if (
            output.contribution_id != descriptor.contribution_id
            or output.affects_feasibility != descriptor.affects_feasibility
            or output.validation_rule_ids != descriptor.validation_rule_ids
        ):
            fail(
                ExtensionErrorCode.INVALID_VALIDATION_PAIR,
                descriptor.contribution_id,
                "Planning Rule output differs from its manifest boundary",
            )
        return
    if descriptor.extension_point is ExtensionPoint.VALIDATION_RULE:
        if not isinstance(context, ValidationContext) or not isinstance(
            output, ValidationOutput
        ):
            fail(
                ExtensionErrorCode.MUTABLE_VALUE,
                descriptor.contribution_id,
                "Validation Rule must return ValidationOutput for its context",
            )
        if (
            output.contribution_id != descriptor.contribution_id
            or output.validated_contribution_ids
            != descriptor.validates_contribution_ids
        ):
            fail(
                ExtensionErrorCode.INVALID_VALIDATION_PAIR,
                descriptor.contribution_id,
                "Validation output target set differs from the manifest pair",
            )
        return
    if descriptor.extension_point is ExtensionPoint.REPLAN_POLICY:
        if not isinstance(context, ReplanContext) or not isinstance(
            output, ReplanDecision
        ):
            fail(
                ExtensionErrorCode.MUTABLE_VALUE,
                descriptor.contribution_id,
                "Replan Policy must return ReplanDecision for ReplanContext",
            )
        context_binding = (
            context.execution_fact_fingerprint,
            context.hard_lock_fingerprint,
            context.freeze_window_fingerprint,
            context.state_machine_version,
            context.publication_authority_reference,
        )
        output_binding = (
            output.execution_fact_fingerprint,
            output.hard_lock_fingerprint,
            output.freeze_window_fingerprint,
            output.state_machine_version,
            output.publication_authority_reference,
        )
        if output.contribution_id != descriptor.contribution_id or output_binding != context_binding:
            fail(
                ExtensionErrorCode.FORBIDDEN_BOUNDARY_ACCESS,
                descriptor.contribution_id,
                "Replan decision must preserve facts, locks, freeze, state, and authority",
            )
        return
    if descriptor.extension_point is ExtensionPoint.PLUGIN_REGISTRY:
        if not isinstance(output, RegistryResolution):
            fail(
                ExtensionErrorCode.MUTABLE_VALUE,
                descriptor.contribution_id,
                "Plugin Registry must return the SDK RegistryResolution value",
            )
        return
    fail(
        ExtensionErrorCode.UNKNOWN_EXTENSION_POINT,
        descriptor.contribution_id,
        "descriptor extension point is not part of SDK v1",
    )


PROTOCOLS_BY_POINT: dict[ExtensionPoint, type[object]] = {
    ExtensionPoint.CONSTRAINT: Constraint,
    ExtensionPoint.OBJECTIVE: Objective,
    ExtensionPoint.PLANNING_RULE: PlanningRule,
    ExtensionPoint.VALIDATION_RULE: ValidationRule,
    ExtensionPoint.REPLAN_POLICY: ReplanPolicy,
    ExtensionPoint.PLUGIN_REGISTRY: PluginRegistry,
}


__all__ = [
    "PROTOCOLS_BY_POINT",
    "Constraint",
    "ConstraintContext",
    "ConstraintOutput",
    "ExtensionInputView",
    "Objective",
    "ObjectiveContext",
    "ObjectiveOutput",
    "ObjectiveSense",
    "PlanningRule",
    "PlanningRuleContext",
    "PlanningRuleOutput",
    "PluginRegistry",
    "ReplanAction",
    "ReplanContext",
    "ReplanDecision",
    "ReplanPolicy",
    "ValidationContext",
    "ValidationOutput",
    "ValidationRule",
    "ValidationViolation",
    "validate_protocol_output",
]
