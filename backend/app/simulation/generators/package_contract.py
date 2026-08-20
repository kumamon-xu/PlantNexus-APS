"""Minimal deterministic Standard Import package output for P0 contract tests."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import NoReturn, cast

from app.data_validation import (
    QualityReportContractError,
    validate_quality_report_contract,
)
from app.domain.canonical_records import (
    CanonicalContractError,
    ImportPackageDocumentV2,
    validate_import_package_v2,
)
from app.domain.contracts import ImportPackageDocument
from app.domain.types import (
    ContractValueError,
    format_utc_instant,
    parse_utc_instant,
)
from app.simulation.generators.contracts import (
    GeneratedScenarioPackage,
    GenerationContext,
    P1_GENERATION_MANIFEST_VERSION,
    SyntheticGenerationManifestDocument,
    SyntheticGeneratorError,
    SyntheticGeneratorErrorCode,
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
    require_identity,
    require_seed,
    require_semver,
    require_simulation_target,
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

    manifest = cast(ScenarioManifestDocument, package.manifest)
    validate_scenario_manifest_contract(manifest)
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
    if import_package.get("scenario_id") != manifest["scenario"]["scenario_id"]:
        raise SimulationContractError(
            SimulationContractCode.INVALID_PROVENANCE,
            "Import scenario_id does not match manifest",
        )
    if import_package["package_id"] != manifest["import_package"]["package_id"]:
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
    if digest != package.dataset_hash or digest != manifest["dataset_hash"]:
        raise SimulationContractError(
            SimulationContractCode.INVALID_PROVENANCE,
            "dataset hash does not match canonical Import package",
        )


def _p1_invalid(message: str) -> NoReturn:
    raise SyntheticGeneratorError(SyntheticGeneratorErrorCode.PACKAGE_INVALID, message)


def validate_p1_generated_scenario_package(
    package: GeneratedScenarioPackage,
) -> None:
    """Validate the generator-local Import v2 manifest and quality evidence."""

    manifest = cast(SyntheticGenerationManifestDocument, package.manifest)
    import_package = cast(ImportPackageDocumentV2, package.import_package)
    if manifest.get("generation_manifest_version") != P1_GENERATION_MANIFEST_VERSION:
        _p1_invalid("unexpected P1 generation manifest version")
    if (
        manifest.get("synthetic") is not True
        or import_package.get("synthetic") is not True
    ):
        _p1_invalid("P1 generator package must remain synthetic")
    try:
        require_simulation_target(manifest["target_environment"])
        require_identity(manifest["scenario"]["scenario_id"], "scenario_id")
        require_semver(manifest["scenario"]["scenario_version"], "scenario_version")
        require_identity(manifest["factory_profile"]["profile_id"], "profile_id")
        require_semver(
            manifest["factory_profile"]["profile_version"], "profile_version"
        )
        require_identity(manifest["generator"]["generator_id"], "generator_id")
        require_semver(manifest["generator"]["generator_version"], "generator_version")
        require_seed(manifest["seed"])
        parse_utc_instant(manifest["generated_at"])
    except (SimulationContractError, ContractValueError, KeyError, TypeError) as error:
        raise SyntheticGeneratorError(
            SyntheticGeneratorErrorCode.PACKAGE_INVALID,
            "P1 generation manifest provenance is invalid",
        ) from error
    if manifest.get("canonicalization_version") != CANONICALIZATION_VERSION:
        _p1_invalid("manifest canonicalization version is invalid")
    if import_package.get("import_package_version") != "import-package.v2":
        _p1_invalid("P1 generator output must use Standard Import v2")
    if manifest["import_package"] != {
        "import_package_version": "import-package.v2",
        "schema_set_version": import_package["schema_set_version"],
        "package_id": import_package["package_id"],
    }:
        _p1_invalid("manifest Import reference does not match canonical package")
    if manifest.get("normalization_rule_version") != import_package.get(
        "normalization_rule_version"
    ):
        _p1_invalid("manifest normalization rule version does not match Import")

    provenance = import_package.get("synthetic_provenance")
    if provenance != {
        "scenario_id": manifest["scenario"]["scenario_id"],
        "scenario_version": manifest["scenario"]["scenario_version"],
        "seed": manifest["seed"],
        "factory_profile_id": manifest["factory_profile"]["profile_id"],
        "profile_version": manifest["factory_profile"]["profile_version"],
        "generator_id": manifest["generator"]["generator_id"],
        "generator_version": manifest["generator"]["generator_version"],
    }:
        _p1_invalid("Import synthetic provenance does not match manifest")
    try:
        validate_import_package_v2(import_package)
    except (CanonicalContractError, KeyError, TypeError) as error:
        raise SyntheticGeneratorError(
            SyntheticGeneratorErrorCode.PACKAGE_INVALID,
            "canonical Import v2 contract validation failed",
        ) from error

    quality_report = package.quality_report
    if quality_report is None:
        _p1_invalid("P1 generated package requires an Import quality report")
    try:
        validate_quality_report_contract(quality_report)
    except QualityReportContractError as error:
        raise SyntheticGeneratorError(
            SyntheticGeneratorErrorCode.PACKAGE_INVALID,
            "Import quality report contract validation failed",
        ) from error
    if quality_report["status"] != "PASS" or quality_report["error_count"] != 0:
        _p1_invalid(
            "P1 generated package quality evidence must be PASS with zero errors"
        )
    if manifest["import_quality_report"] != {
        "report_version": quality_report["report_version"],
        "report_id": quality_report["report_id"],
        "status": quality_report["status"],
        "error_count": quality_report["error_count"],
    }:
        _p1_invalid("manifest quality report reference does not match evidence")
    if quality_report["package_id"] != import_package["package_id"]:
        _p1_invalid("quality report does not reference the generated Import package")

    canonical_dataset = canonical_json_bytes(import_package)
    if canonical_dataset != package.canonical_dataset:
        _p1_invalid("canonical dataset bytes do not match Import v2")
    digest = dataset_sha256(canonical_dataset)
    if digest != package.dataset_hash or digest != manifest.get("dataset_hash"):
        _p1_invalid("dataset hash does not match canonical Import v2")


__all__ = [
    "build_empty_import_package",
    "validate_generated_scenario_package",
    "validate_p1_generated_scenario_package",
]
