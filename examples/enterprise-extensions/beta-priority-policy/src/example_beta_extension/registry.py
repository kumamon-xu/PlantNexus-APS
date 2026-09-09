"""SDK-authoritative deterministic Plugin Registry implementation."""

from __future__ import annotations

from aps_extension_sdk import (
    CompatibilityPolicy,
    ContributionManifest,
    ExtensionManifest,
    RegistryResolution,
    resolve_manifest_set,
)


class BetaRegistry:
    def __init__(self, descriptor: ContributionManifest) -> None:
        self._descriptor = descriptor

    @property
    def descriptor(self) -> ContributionManifest:
        return self._descriptor

    def resolve(
        self,
        manifests: tuple[ExtensionManifest, ...],
        compatibility: CompatibilityPolicy,
    ) -> RegistryResolution:
        return resolve_manifest_set(manifests, compatibility)


__all__ = ["BetaRegistry"]
