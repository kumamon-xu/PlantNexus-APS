"""Synthetic resource-tag Constraint starter."""

from __future__ import annotations

from collections.abc import Mapping

from aps_extension_sdk import (
    ConstraintContext,
    ConstraintOutput,
    ContributionManifest,
    FrozenJsonObject,
    freeze_json,
)


def _required_tag(context: ConstraintContext) -> str:
    extension_configuration = context.input_view.scope.get("extension_configuration")
    if not isinstance(extension_configuration, Mapping):
        return "qualified"
    values = extension_configuration.get("values")
    if not isinstance(values, Mapping):
        return "qualified"
    value = values.get("required_tag")
    return value if isinstance(value, str) and value else "qualified"


class ResourceTagConstraint:
    def __init__(self, descriptor: ContributionManifest) -> None:
        self._descriptor = descriptor

    @property
    def descriptor(self) -> ContributionManifest:
        return self._descriptor

    def contribute(self, context: ConstraintContext) -> ConstraintOutput:
        required_tag = _required_tag(context)
        resources = context.input_view.facts.get("resources", ())
        qualified: list[str] = []
        if isinstance(resources, tuple):
            for resource in resources:
                if not isinstance(resource, FrozenJsonObject):
                    continue
                resource_id = resource.get("resource_id")
                tags = resource.get("tags", ())
                if (
                    isinstance(resource_id, str)
                    and isinstance(tags, tuple)
                    and required_tag in tags
                ):
                    qualified.append(resource_id)
        specification = freeze_json(
            {
                "kind": "synthetic.resource_tag_eligibility",
                "qualified_resource_ids": sorted(set(qualified)),
                "required_tag": required_tag,
            }
        )
        assert isinstance(specification, FrozenJsonObject)
        return ConstraintOutput(
            contribution_id=self.descriptor.contribution_id,
            constraint_contract_version="enterprise.resource_tag.constraint.v1",
            constraint_specification=specification,
            validation_rule_ids=self.descriptor.validation_rule_ids,
        )


__all__ = ["ResourceTagConstraint"]
