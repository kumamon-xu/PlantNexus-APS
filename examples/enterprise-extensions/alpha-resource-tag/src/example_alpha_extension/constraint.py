"""Alpha solver-neutral resource-tag contribution."""

from __future__ import annotations

from collections.abc import Mapping

from aps_extension_sdk import (
    ConstraintContext,
    ConstraintOutput,
    ContributionManifest,
    FrozenJsonObject,
    freeze_json,
)


class AlphaResourceTagConstraint:
    def __init__(self, descriptor: ContributionManifest) -> None:
        self._descriptor = descriptor

    @property
    def descriptor(self) -> ContributionManifest:
        return self._descriptor

    def contribute(self, context: ConstraintContext) -> ConstraintOutput:
        configuration = context.input_view.scope.get("extension_configuration")
        values = (
            configuration.get("values") if isinstance(configuration, Mapping) else None
        )
        configured = values.get("required_tag") if isinstance(values, Mapping) else None
        required_tag = configured if isinstance(configured, str) else "alpha-qualified"
        resource_ids: list[str] = []
        resources = context.input_view.facts.get("resources", ())
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
                    resource_ids.append(resource_id)
        specification = freeze_json(
            {
                "eligible_resource_ids": sorted(set(resource_ids)),
                "kind": "synthetic.alpha.resource_tag",
                "required_tag": required_tag,
            }
        )
        assert isinstance(specification, FrozenJsonObject)
        return ConstraintOutput(
            contribution_id=self.descriptor.contribution_id,
            constraint_contract_version="synthetic.alpha.resource_tag.v1",
            constraint_specification=specification,
            validation_rule_ids=self.descriptor.validation_rule_ids,
        )


__all__ = ["AlphaResourceTagConstraint"]
