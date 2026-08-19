"""Minimal deterministic Standard Import package output for P0 contract tests."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import cast

from app.domain.contracts import ImportPackageDocument
from app.domain.types import format_utc_instant
from app.simulation.generators.contracts import (
    GeneratedScenarioPackage,
    GenerationContext,
)
from app.simulation.generators.determinism import (
    CANONICALIZATION_VERSION,
    canonical_json_bytes,
    dataset_sha256,
)
from app.simulation.scenarios.contracts import (
    ScenarioManifestDocument,
    SimulationContractCode,
    SimulationContractError,
    validate_scenario_manifest_contract,
)


def _package_id(context: GenerationContext) -> str:
    identity = canonical_json_bytes(
        {
            "generator_id": context.generator_id,
            "generator_version": context.generator_version,
            "profile_id": context.profile_id,
            "profile_version": context.profile_version,
            "required_capabilities": [
                name.value for name in context.required_capabilities
            ],
            "scenario_id": context.scenario_id,
            "scenario_version": context.scenario_version,
            "seed": context.seed,
        }
    )
    suffix = hashlib.sha256(identity).hexdigest()[:24].upper()
    return f"SIMPKG-{suffix}"


def build_empty_import_package(
    context: GenerationContext, *, generated_at: datetime | None = None
) -> GeneratedScenarioPackage:
    """Build an empty Import v1 envelope without guessing canonical entity fields."""

    package = cast(
        ImportPackageDocument,
        {
            "import_package_version": "import-package.v1",
            "package_id": _package_id(context),
            "source_versions": {
                "factory_profile": context.profile_version,
                "scenario": context.scenario_version,
                "synthetic_generator": context.generator_version,
            },
            "synthetic": True,
            "scenario_id": context.scenario_id,
            "records": {},
        },
    )
    canonical_dataset = canonical_json_bytes(package)
    dataset_hash = dataset_sha256(canonical_dataset)
    manifest = cast(
        ScenarioManifestDocument,
        {
            "scenario_manifest_version": "scenario-manifest.v1",
            "synthetic": True,
            "target_environment": context.target.value,
            "scenario": {
                "scenario_id": context.scenario_id,
                "scenario_version": context.scenario_version,
            },
            "factory_profile": {
                "profile_id": context.profile_id,
                "profile_version": context.profile_version,
            },
            "generator": {
                "generator_id": context.generator_id,
                "generator_version": context.generator_version,
            },
            "seed": context.seed,
            "required_capabilities": [
                name.value for name in context.required_capabilities
            ],
            "generated_at": format_utc_instant(generated_at or datetime.now(UTC)),
            "canonicalization_version": CANONICALIZATION_VERSION,
            "import_package": {
                "import_package_version": "import-package.v1",
                "package_id": package["package_id"],
            },
            "dataset_hash": dataset_hash,
        },
    )
    generated = GeneratedScenarioPackage(
        import_package=package,
        manifest=manifest,
        canonical_dataset=canonical_dataset,
        dataset_hash=dataset_hash,
    )
    validate_generated_scenario_package(generated)
    return generated


def validate_generated_scenario_package(package: GeneratedScenarioPackage) -> None:
    """Check canonical bytes, hash, manifest, and synthetic Import isolation."""

    validate_scenario_manifest_contract(package.manifest)
    import_package = package.import_package
    if import_package["import_package_version"] != "import-package.v1":
        raise SimulationContractError(
            SimulationContractCode.INVALID_VERSION,
            "generator output must use Standard Import v1",
        )
    if import_package["synthetic"] is not True:
        raise SimulationContractError(
            SimulationContractCode.PRODUCTION_TARGET_FORBIDDEN,
            "generator output must be synthetic=true",
        )
    if import_package.get("scenario_id") != package.manifest["scenario"]["scenario_id"]:
        raise SimulationContractError(
            SimulationContractCode.INVALID_PROVENANCE,
            "Import scenario_id does not match manifest",
        )
    if import_package["package_id"] != package.manifest["import_package"]["package_id"]:
        raise SimulationContractError(
            SimulationContractCode.INVALID_PROVENANCE,
            "Import package_id does not match manifest",
        )
    canonical_dataset = canonical_json_bytes(import_package)
    if canonical_dataset != package.canonical_dataset:
        raise SimulationContractError(
            SimulationContractCode.INVALID_PROVENANCE,
            "canonical dataset bytes do not match Import package",
        )
    digest = dataset_sha256(canonical_dataset)
    if digest != package.dataset_hash or digest != package.manifest["dataset_hash"]:
        raise SimulationContractError(
            SimulationContractCode.INVALID_PROVENANCE,
            "dataset hash does not match canonical Import package",
        )


__all__ = ["build_empty_import_package", "validate_generated_scenario_package"]
