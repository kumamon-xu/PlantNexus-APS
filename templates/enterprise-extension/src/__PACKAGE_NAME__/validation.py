"""Independent synthetic resource-tag Validation Rule starter."""

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


def _configured_tag(context: ValidationContext) -> str:
    configuration = context.input_view.scope.get("extension_configuration")
    if not isinstance(configuration, Mapping):
        return "qualified"
    values = configuration.get("values")
    if not isinstance(values, Mapping):
        return "qualified"
    required = values.get("required_tag")
    return required if isinstance(required, str) and required else "qualified"


class ResourceTagValidationRule:
    def __init__(self, descriptor: ContributionManifest) -> None:
        self._descriptor = descriptor

    @property
    def descriptor(self) -> ContributionManifest:
        return self._descriptor

    def validate(self, context: ValidationContext) -> ValidationOutput:
        required_tag = _configured_tag(context)
        resources = context.input_view.facts.get("resources", ())
        assignments = context.input_view.facts.get("assignments", ())
        tags_by_resource: dict[str, tuple[object, ...]] = {}
        if isinstance(resources, tuple):
            for resource in resources:
                if isinstance(resource, FrozenJsonObject):
                    resource_id = resource.get("resource_id")
                    tags = resource.get("tags", ())
                    if isinstance(resource_id, str) and isinstance(tags, tuple):
                        tags_by_resource[resource_id] = tags
        ordered_assignments: list[tuple[str, str]] = []
        if isinstance(assignments, tuple):
            for assignment in assignments:
                if isinstance(assignment, FrozenJsonObject):
                    operation_id = assignment.get("operation_id")
                    resource_id = assignment.get("resource_id")
                    if isinstance(operation_id, str) and isinstance(resource_id, str):
                        ordered_assignments.append((operation_id, resource_id))
        violations: list[ValidationViolation] = []
        for operation_id, resource_id in sorted(ordered_assignments):
            if required_tag in tags_by_resource.get(resource_id, ()):
                continue
            observed = freeze_json({"resource_id": resource_id})
            expected = freeze_json({"required_tag": required_tag})
            assert isinstance(observed, FrozenJsonObject)
            assert isinstance(expected, FrozenJsonObject)
            violations.append(
                ValidationViolation(
                    violation_code="enterprise.resource_tag.missing",
                    entity_ids=tuple(sorted((operation_id, resource_id))),
                    path="$.assignments",
                    observed=observed,
                    expected=expected,
                    message_key="enterprise.resource_tag.missing",
                )
            )
        return ValidationOutput(
            contribution_id=self.descriptor.contribution_id,
            validated_contribution_ids=self.descriptor.validates_contribution_ids,
            passed=not violations,
            violations=tuple(violations),
        )


__all__ = ["ResourceTagValidationRule"]
