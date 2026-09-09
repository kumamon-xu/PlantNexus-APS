"""Alpha independent assignment validator; does not import Constraint code."""

from __future__ import annotations

from collections.abc import Mapping

from aps_extension_sdk import (
    ContributionManifest,
    FrozenJsonObject,
    ValidationContext,
    ValidationOutput,
    ValidationViolation,
    freeze_json,
)


class AlphaResourceTagValidator:
    def __init__(self, descriptor: ContributionManifest) -> None:
        self._descriptor = descriptor

    @property
    def descriptor(self) -> ContributionManifest:
        return self._descriptor

    def validate(self, context: ValidationContext) -> ValidationOutput:
        configuration = context.input_view.scope.get("extension_configuration")
        values = (
            configuration.get("values") if isinstance(configuration, Mapping) else None
        )
        configured = values.get("required_tag") if isinstance(values, Mapping) else None
        required_tag = configured if isinstance(configured, str) else "alpha-qualified"
        qualified: set[str] = set()
        resources = context.input_view.facts.get("resources", ())
        if isinstance(resources, tuple):
            for resource in resources:
                if isinstance(resource, FrozenJsonObject):
                    resource_id = resource.get("resource_id")
                    tags = resource.get("tags", ())
                    if (
                        isinstance(resource_id, str)
                        and isinstance(tags, tuple)
                        and required_tag in tags
                    ):
                        qualified.add(resource_id)
        pairs: list[tuple[str, str]] = []
        assignments = context.input_view.facts.get("assignments", ())
        if isinstance(assignments, tuple):
            for assignment in assignments:
                if isinstance(assignment, FrozenJsonObject):
                    operation_id = assignment.get("operation_id")
                    resource_id = assignment.get("resource_id")
                    if isinstance(operation_id, str) and isinstance(resource_id, str):
                        pairs.append((operation_id, resource_id))
        violations: list[ValidationViolation] = []
        for operation_id, resource_id in sorted(pairs):
            if resource_id in qualified:
                continue
            observed = freeze_json({"resource_id": resource_id})
            expected = freeze_json({"required_tag": required_tag})
            assert isinstance(observed, FrozenJsonObject)
            assert isinstance(expected, FrozenJsonObject)
            violations.append(
                ValidationViolation(
                    violation_code="synthetic.alpha.resource_tag.missing",
                    entity_ids=tuple(sorted((operation_id, resource_id))),
                    path="$.assignments",
                    observed=observed,
                    expected=expected,
                    message_key="synthetic.alpha.resource_tag.missing",
                )
            )
        return ValidationOutput(
            contribution_id=self.descriptor.contribution_id,
            validated_contribution_ids=self.descriptor.validates_contribution_ids,
            passed=not violations,
            violations=tuple(violations),
        )


__all__ = ["AlphaResourceTagValidator"]
