"""Strict manifest, compatibility, pairing, and registry-resolution contracts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import NoReturn, cast

from aps_extension_sdk.errors import ExtensionErrorCode, fail
from aps_extension_sdk.values import (
    SemanticVersion,
    VersionInterval,
    fingerprint_json,
    require_commit,
    require_entrypoint,
    require_fingerprint,
    require_identifier,
    require_sorted_unique_text,
)


SDK_API_VERSION = "1.0.0"
EXTENSION_MANIFEST_VERSION = "extension-manifest.v1"
EXTENSION_COMPATIBILITY_VERSION = "extension-compatibility.v1"
REGISTRY_PROTOCOL_VERSION = "plugin-registry.v1"


class ExtensionPoint(StrEnum):
    CONSTRAINT = "CONSTRAINT"
    OBJECTIVE = "OBJECTIVE"
    PLANNING_RULE = "PLANNING_RULE"
    VALIDATION_RULE = "VALIDATION_RULE"
    REPLAN_POLICY = "REPLAN_POLICY"
    PLUGIN_REGISTRY = "PLUGIN_REGISTRY"


class ExecutionDomain(StrEnum):
    SOLVER = "SOLVER"
    PLANNING = "PLANNING"
    VALIDATOR = "VALIDATOR"
    REPLAN = "REPLAN"
    REGISTRY = "REGISTRY"


class ObjectiveStage(StrEnum):
    """The only v1 enterprise slot; Core stage order remains closed."""

    ENTERPRISE_TIE_BREAK = "ENTERPRISE_TIE_BREAK"


SPI_VERSIONS: Mapping[ExtensionPoint, str] = {
    ExtensionPoint.CONSTRAINT: "constraint.v1",
    ExtensionPoint.OBJECTIVE: "objective.v1",
    ExtensionPoint.PLANNING_RULE: "planning-rule.v1",
    ExtensionPoint.VALIDATION_RULE: "validation-rule.v1",
    ExtensionPoint.REPLAN_POLICY: "replan-policy.v1",
    ExtensionPoint.PLUGIN_REGISTRY: REGISTRY_PROTOCOL_VERSION,
}

EXECUTION_DOMAINS: Mapping[ExtensionPoint, ExecutionDomain] = {
    ExtensionPoint.CONSTRAINT: ExecutionDomain.SOLVER,
    ExtensionPoint.OBJECTIVE: ExecutionDomain.SOLVER,
    ExtensionPoint.PLANNING_RULE: ExecutionDomain.PLANNING,
    ExtensionPoint.VALIDATION_RULE: ExecutionDomain.VALIDATOR,
    ExtensionPoint.REPLAN_POLICY: ExecutionDomain.REPLAN,
    ExtensionPoint.PLUGIN_REGISTRY: ExecutionDomain.REGISTRY,
}


@dataclass(frozen=True, slots=True)
class ContributionManifest:
    contribution_id: str
    extension_point: ExtensionPoint
    spi_version: str
    implementation: str
    execution_domain: ExecutionDomain
    order: int
    capabilities: tuple[str, ...]
    affects_feasibility: bool
    validation_rule_ids: tuple[str, ...]
    validates_contribution_ids: tuple[str, ...]
    objective_stage: ObjectiveStage | None


@dataclass(frozen=True, slots=True)
class ExtensionManifest:
    manifest_version: str
    sdk_api_version: SemanticVersion
    extension_id: str
    extension_version: SemanticVersion
    artifact_digest: str
    artifact_package: str
    configuration_contract: str
    configuration_schema_digest: str
    sdk_compatibility: VersionInterval
    runtime_compatibility: VersionInterval
    registry_protocol_version: str
    contributions: tuple[ContributionManifest, ...]
    requested_services: tuple[str, ...]
    source_commit: str
    dependency_lock_digest: str
    manifest_fingerprint: str


@dataclass(frozen=True, slots=True)
class CompatibilityPolicy:
    compatibility_version: str
    sdk_api_version: SemanticVersion
    supported_sdk_range: VersionInterval
    supported_manifest_versions: tuple[str, ...]
    supported_registry_protocol_versions: tuple[str, ...]
    supported_extension_points: tuple[ExtensionPoint, ...]
    compatibility_fingerprint: str


@dataclass(frozen=True, slots=True)
class RegistryResolution:
    sdk_api_version: SemanticVersion
    extension_ids: tuple[str, ...]
    manifest_fingerprints: tuple[str, ...]
    contributions: tuple[ContributionManifest, ...]
    resolution_fingerprint: str


def _reject(code: ExtensionErrorCode, field: str, message: str) -> NoReturn:
    fail(code, field, message)


def _object(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        _reject(ExtensionErrorCode.INVALID_MANIFEST, field, "value must be an object")
    return cast(Mapping[str, object], value)


def _array(value: object, field: str) -> list[object]:
    if not isinstance(value, list):
        _reject(ExtensionErrorCode.INVALID_MANIFEST, field, "value must be an array")
    return cast(list[object], value)


def _exact_keys(value: Mapping[str, object], expected: set[str], field: str) -> None:
    observed = set(value)
    if observed != expected:
        _reject(
            ExtensionErrorCode.INVALID_MANIFEST,
            field,
            "object keys do not match the exact contract",
        )


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        _reject(
            ExtensionErrorCode.INVALID_MANIFEST,
            field,
            "value must be non-empty text",
        )
    return value


def _boolean(value: object, field: str) -> bool:
    if not isinstance(value, bool):
        _reject(ExtensionErrorCode.INVALID_MANIFEST, field, "value must be boolean")
    return value


def _integer(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 10_000:
        _reject(
            ExtensionErrorCode.INVALID_MANIFEST,
            field,
            "order must be an integer from 0 through 10000",
        )
    return value


def _interval(value: object, field: str) -> VersionInterval:
    document = _object(value, field)
    _exact_keys(document, {"minimum_inclusive", "maximum_exclusive"}, field)
    return VersionInterval(
        SemanticVersion.parse(
            document["minimum_inclusive"], field=f"{field}.minimum_inclusive"
        ),
        SemanticVersion.parse(
            document["maximum_exclusive"], field=f"{field}.maximum_exclusive"
        ),
    )


def _parse_contribution(value: object, index: int) -> ContributionManifest:
    field = f"contributions[{index}]"
    document = _object(value, field)
    expected = {
        "contribution_id",
        "extension_point",
        "spi_version",
        "implementation",
        "execution_domain",
        "order",
        "capabilities",
        "affects_feasibility",
        "validation_rule_ids",
        "validates_contribution_ids",
        "objective_stage",
    }
    _exact_keys(document, expected, field)
    point_text = _text(document["extension_point"], f"{field}.extension_point")
    try:
        point = ExtensionPoint(point_text)
    except ValueError:
        _reject(
            ExtensionErrorCode.UNKNOWN_EXTENSION_POINT,
            f"{field}.extension_point",
            "extension point is not part of SDK v1",
        )
    domain_text = _text(document["execution_domain"], f"{field}.execution_domain")
    try:
        domain = ExecutionDomain(domain_text)
    except ValueError:
        _reject(
            ExtensionErrorCode.FORBIDDEN_BOUNDARY_ACCESS,
            f"{field}.execution_domain",
            "execution domain is not exposed by SDK v1",
        )
    if domain is not EXECUTION_DOMAINS[point]:
        _reject(
            ExtensionErrorCode.FORBIDDEN_BOUNDARY_ACCESS,
            f"{field}.execution_domain",
            "extension point is assigned to a different closed execution domain",
        )
    spi_version = _text(document["spi_version"], f"{field}.spi_version")
    if spi_version != SPI_VERSIONS[point]:
        _reject(
            ExtensionErrorCode.UNSUPPORTED_MANIFEST_VERSION,
            f"{field}.spi_version",
            "SPI version does not match the declared extension point",
        )
    objective_stage_value = document["objective_stage"]
    objective_stage: ObjectiveStage | None = None
    if point is ExtensionPoint.OBJECTIVE:
        try:
            objective_stage = ObjectiveStage(
                _text(objective_stage_value, f"{field}.objective_stage")
            )
        except ValueError:
            _reject(
                ExtensionErrorCode.INVALID_OBJECTIVE_STAGE,
                f"{field}.objective_stage",
                "SDK v1 only permits the enterprise tie-break stage",
            )
    elif objective_stage_value is not None:
        _reject(
            ExtensionErrorCode.INVALID_OBJECTIVE_STAGE,
            f"{field}.objective_stage",
            "non-objective contributions must use null",
        )

    affects_feasibility = _boolean(
        document["affects_feasibility"], f"{field}.affects_feasibility"
    )
    if point is ExtensionPoint.CONSTRAINT and not affects_feasibility:
        _reject(
            ExtensionErrorCode.MISSING_VALIDATION_PAIR,
            f"{field}.affects_feasibility",
            "Constraint contributions always affect feasibility",
        )
    if point not in {ExtensionPoint.CONSTRAINT, ExtensionPoint.PLANNING_RULE} and affects_feasibility:
        _reject(
            ExtensionErrorCode.INVALID_VALIDATION_PAIR,
            f"{field}.affects_feasibility",
            "this extension point cannot declare a feasibility effect",
        )

    validation_ids = require_sorted_unique_text(
        document["validation_rule_ids"],
        field=f"{field}.validation_rule_ids",
        allow_empty=not affects_feasibility,
    )
    validates_ids = require_sorted_unique_text(
        document["validates_contribution_ids"],
        field=f"{field}.validates_contribution_ids",
        allow_empty=point is not ExtensionPoint.VALIDATION_RULE,
    )
    capabilities = require_sorted_unique_text(
        document["capabilities"],
        field=f"{field}.capabilities",
        allow_empty=True,
    )
    for name, values in (
        ("capabilities", capabilities),
        ("validation_rule_ids", validation_ids),
        ("validates_contribution_ids", validates_ids),
    ):
        for value in values:
            require_identifier(value, field=f"{field}.{name}")
    if not affects_feasibility and validation_ids:
        _reject(
            ExtensionErrorCode.INVALID_VALIDATION_PAIR,
            f"{field}.validation_rule_ids",
            "non-feasibility contributions cannot claim a validator pair",
        )
    if point is not ExtensionPoint.VALIDATION_RULE and validates_ids:
        _reject(
            ExtensionErrorCode.INVALID_VALIDATION_PAIR,
            f"{field}.validates_contribution_ids",
            "only Validation Rule contributions can validate another contribution",
        )

    return ContributionManifest(
        contribution_id=require_identifier(
            document["contribution_id"], field=f"{field}.contribution_id"
        ),
        extension_point=point,
        spi_version=spi_version,
        implementation=require_entrypoint(
            document["implementation"], field=f"{field}.implementation"
        ),
        execution_domain=domain,
        order=_integer(document["order"], f"{field}.order"),
        capabilities=capabilities,
        affects_feasibility=affects_feasibility,
        validation_rule_ids=validation_ids,
        validates_contribution_ids=validates_ids,
        objective_stage=objective_stage,
    )


def _validate_pairs(contributions: tuple[ContributionManifest, ...]) -> None:
    by_id = {item.contribution_id: item for item in contributions}
    if len(by_id) != len(contributions):
        _reject(
            ExtensionErrorCode.DUPLICATE_CONTRIBUTION_ID,
            "contributions",
            "contribution IDs must be unique within an Extension manifest",
        )
    for item in contributions:
        if item.affects_feasibility:
            for validation_id in item.validation_rule_ids:
                validation = by_id.get(validation_id)
                if validation is None:
                    _reject(
                        ExtensionErrorCode.MISSING_VALIDATION_PAIR,
                        item.contribution_id,
                        "paired Validation Rule is absent from the same artifact",
                    )
                if (
                    validation.extension_point is not ExtensionPoint.VALIDATION_RULE
                    or item.contribution_id not in validation.validates_contribution_ids
                    or validation.implementation == item.implementation
                ):
                    _reject(
                        ExtensionErrorCode.INVALID_VALIDATION_PAIR,
                        item.contribution_id,
                        "pair must be symmetric and use an independent validator entrypoint",
                    )
        if item.extension_point is ExtensionPoint.VALIDATION_RULE:
            for target_id in item.validates_contribution_ids:
                target = by_id.get(target_id)
                if (
                    target is None
                    or not target.affects_feasibility
                    or item.contribution_id not in target.validation_rule_ids
                ):
                    _reject(
                        ExtensionErrorCode.INVALID_VALIDATION_PAIR,
                        item.contribution_id,
                        "Validation Rule target must symmetrically declare the pair",
                    )


def parse_extension_manifest(document: Mapping[str, object]) -> ExtensionManifest:
    """Parse one exact v1 manifest and reject every unknown or unsafe variant."""

    expected = {
        "extension_manifest_version",
        "sdk_api_version",
        "extension_id",
        "extension_version",
        "artifact",
        "configuration",
        "compatibility",
        "registry_protocol_version",
        "contributions",
        "requested_services",
        "provenance",
        "execution_boundary",
        "manifest_fingerprint",
    }
    _exact_keys(document, expected, "$manifest")
    if document["extension_manifest_version"] != EXTENSION_MANIFEST_VERSION:
        _reject(
            ExtensionErrorCode.UNSUPPORTED_MANIFEST_VERSION,
            "extension_manifest_version",
            "only extension-manifest.v1 is supported",
        )
    if document["registry_protocol_version"] != REGISTRY_PROTOCOL_VERSION:
        _reject(
            ExtensionErrorCode.UNSUPPORTED_REGISTRY_PROTOCOL,
            "registry_protocol_version",
            "only plugin-registry.v1 is supported",
        )

    artifact = _object(document["artifact"], "artifact")
    _exact_keys(artifact, {"digest", "media_type", "package"}, "artifact")
    if artifact["media_type"] != "application/vnd.plantnexus.aps-extension+python":
        _reject(
            ExtensionErrorCode.INVALID_MANIFEST,
            "artifact.media_type",
            "artifact media type is not an APS Python Extension",
        )
    configuration = _object(document["configuration"], "configuration")
    _exact_keys(
        configuration,
        {"contract_version", "schema_digest"},
        "configuration",
    )
    compatibility = _object(document["compatibility"], "compatibility")
    _exact_keys(
        compatibility,
        {"sdk", "runtime"},
        "compatibility",
    )
    provenance = _object(document["provenance"], "provenance")
    _exact_keys(
        provenance,
        {"source_commit", "dependency_lock_digest", "reproducible_build"},
        "provenance",
    )
    if provenance["reproducible_build"] is not True:
        _reject(
            ExtensionErrorCode.INVALID_MANIFEST,
            "provenance.reproducible_build",
            "v1 artifacts must declare reproducible_build=true",
        )
    boundary = _object(document["execution_boundary"], "execution_boundary")
    expected_boundary = {
        "load_phase": "BUILD_DEPLOY_STARTUP_ONLY",
        "trusted_in_process": True,
        "sandboxed": False,
        "request_code_selection": False,
        "network_install": False,
        "external_api": False,
        "database_access": False,
    }
    _exact_keys(boundary, set(expected_boundary), "execution_boundary")
    if dict(boundary) != expected_boundary:
        _reject(
            ExtensionErrorCode.FORBIDDEN_BOUNDARY_ACCESS,
            "execution_boundary",
            "Extension execution must preserve the closed Runtime boundary",
        )

    contributions = tuple(
        _parse_contribution(item, index)
        for index, item in enumerate(_array(document["contributions"], "contributions"))
    )
    if not contributions:
        _reject(
            ExtensionErrorCode.INVALID_MANIFEST,
            "contributions",
            "an Extension manifest must declare at least one contribution",
        )
    expected_order = tuple(
        sorted(contributions, key=lambda item: (item.order, item.contribution_id))
    )
    if contributions != expected_order:
        _reject(
            ExtensionErrorCode.REGISTRY_CONFLICT,
            "contributions",
            "contributions must be ordered by order then contribution_id",
        )
    _validate_pairs(contributions)

    requested_services = require_sorted_unique_text(
        document["requested_services"],
        field="requested_services",
        allow_empty=True,
    )
    if requested_services:
        _reject(
            ExtensionErrorCode.FORBIDDEN_BOUNDARY_ACCESS,
            "requested_services",
            "SDK v1 exposes immutable inputs only and no privileged services",
        )

    provided_fingerprint = require_fingerprint(
        document["manifest_fingerprint"], field="manifest_fingerprint"
    )
    projection = dict(document)
    projection.pop("manifest_fingerprint")
    if fingerprint_json(projection) != provided_fingerprint:
        _reject(
            ExtensionErrorCode.FINGERPRINT_MISMATCH,
            "manifest_fingerprint",
            "manifest fingerprint does not match canonical content",
        )

    return ExtensionManifest(
        manifest_version=EXTENSION_MANIFEST_VERSION,
        sdk_api_version=SemanticVersion.parse(
            document["sdk_api_version"], field="sdk_api_version"
        ),
        extension_id=require_identifier(document["extension_id"], field="extension_id"),
        extension_version=SemanticVersion.parse(
            document["extension_version"], field="extension_version"
        ),
        artifact_digest=require_fingerprint(artifact["digest"], field="artifact.digest"),
        artifact_package=require_identifier(artifact["package"], field="artifact.package"),
        configuration_contract=require_identifier(
            configuration["contract_version"], field="configuration.contract_version"
        ),
        configuration_schema_digest=require_fingerprint(
            configuration["schema_digest"], field="configuration.schema_digest"
        ),
        sdk_compatibility=_interval(compatibility["sdk"], "compatibility.sdk"),
        runtime_compatibility=_interval(
            compatibility["runtime"], "compatibility.runtime"
        ),
        registry_protocol_version=REGISTRY_PROTOCOL_VERSION,
        contributions=contributions,
        requested_services=requested_services,
        source_commit=require_commit(
            provenance["source_commit"], field="provenance.source_commit"
        ),
        dependency_lock_digest=require_fingerprint(
            provenance["dependency_lock_digest"],
            field="provenance.dependency_lock_digest",
        ),
        manifest_fingerprint=provided_fingerprint,
    )


def parse_compatibility_policy(document: Mapping[str, object]) -> CompatibilityPolicy:
    expected = {
        "extension_compatibility_version",
        "sdk_api_version",
        "supported_sdk_range",
        "supported_manifest_versions",
        "supported_registry_protocol_versions",
        "supported_extension_points",
        "objective_policy",
        "validation_policy",
        "replan_policy_boundary",
        "release_policy",
        "deprecation_policy",
        "contract_status",
        "runtime_loader_status",
        "developer_kit_status",
        "compatibility_fingerprint",
    }
    _exact_keys(document, expected, "$compatibility")
    if document["extension_compatibility_version"] != EXTENSION_COMPATIBILITY_VERSION:
        _reject(
            ExtensionErrorCode.UNSUPPORTED_MANIFEST_VERSION,
            "extension_compatibility_version",
            "only extension-compatibility.v1 is supported",
        )
    release = _object(document["release_policy"], "release_policy")
    objective_policy = _object(document["objective_policy"], "objective_policy")
    expected_objective_policy = {
        "stage": "ENTERPRISE_TIE_BREAK",
        "position": "AFTER_OBJ_003",
        "core_order": ["OBJ-001", "OBJ-002", "OBJ-003"],
        "integer_only": True,
        "implicit_weight": False,
    }
    _exact_keys(objective_policy, set(expected_objective_policy), "objective_policy")
    if dict(objective_policy) != expected_objective_policy:
        _reject(
            ExtensionErrorCode.INVALID_OBJECTIVE_STAGE,
            "objective_policy",
            "enterprise objective must be an integer tie-break after all Core stages",
        )
    validation_policy = _object(document["validation_policy"], "validation_policy")
    expected_validation_policy = {
        "feasibility_pair_required": True,
        "independent_entrypoint": True,
        "solver_status_authority": False,
    }
    _exact_keys(
        validation_policy,
        set(expected_validation_policy),
        "validation_policy",
    )
    if dict(validation_policy) != expected_validation_policy:
        _reject(
            ExtensionErrorCode.INVALID_VALIDATION_PAIR,
            "validation_policy",
            "feasibility contribution must retain independent validation",
        )
    replan_boundary = _object(
        document["replan_policy_boundary"], "replan_policy_boundary"
    )
    expected_replan_boundary = {
        "preserve_execution_facts": True,
        "preserve_hard_locks": True,
        "preserve_freeze_window": True,
        "preserve_state_machine": True,
        "preserve_publication_authority": True,
        "direct_schedule_mutation": False,
    }
    _exact_keys(
        replan_boundary,
        set(expected_replan_boundary),
        "replan_policy_boundary",
    )
    if dict(replan_boundary) != expected_replan_boundary:
        _reject(
            ExtensionErrorCode.FORBIDDEN_BOUNDARY_ACCESS,
            "replan_policy_boundary",
            "Replan Policy cannot override facts, locks, freeze, state, or authority",
        )
    expected_release = {
        "patch": "NO_BUSINESS_SEMANTIC_CHANGE",
        "minor": "ADDITIVE_OPTIONAL",
        "major": "BREAKING_REQUIRES_NEW_DEVELOPER_KIT",
        "exact_lock_required": True,
        "automatic_upgrade": False,
    }
    _exact_keys(release, set(expected_release), "release_policy")
    if dict(release) != expected_release:
        _reject(
            ExtensionErrorCode.INCOMPATIBLE_SDK_VERSION,
            "release_policy",
            "SemVer and exact-lock policy differs from SDK v1",
        )
    deprecation = _object(document["deprecation_policy"], "deprecation_policy")
    expected_deprecation = {
        "removal_requires_new_sdk_major": True,
        "replacement_required": True,
        "support_end_requires_explicit_release": True,
        "silent_replacement": False,
    }
    _exact_keys(deprecation, set(expected_deprecation), "deprecation_policy")
    if dict(deprecation) != expected_deprecation:
        _reject(
            ExtensionErrorCode.DEPRECATED_UNSUPPORTED,
            "deprecation_policy",
            "deprecation cannot silently remove or replace a public SPI",
        )
    statuses = {
        "contract_status": "SDK_CONTRACT_ONLY",
        "runtime_loader_status": "NOT_IMPLEMENTED_UNTIL_P8_13",
        "developer_kit_status": "NOT_IMPLEMENTED_UNTIL_P8_15",
    }
    for key, expected_value in statuses.items():
        if document[key] != expected_value:
            _reject(
                ExtensionErrorCode.FORBIDDEN_BOUNDARY_ACCESS,
                key,
                "carrier must not claim an unimplemented Runtime or Developer Kit",
            )
    manifest_versions = require_sorted_unique_text(
        document["supported_manifest_versions"],
        field="supported_manifest_versions",
        allow_empty=False,
    )
    registry_versions = require_sorted_unique_text(
        document["supported_registry_protocol_versions"],
        field="supported_registry_protocol_versions",
        allow_empty=False,
    )
    point_values = require_sorted_unique_text(
        document["supported_extension_points"],
        field="supported_extension_points",
        allow_empty=False,
    )
    try:
        points = tuple(ExtensionPoint(value) for value in point_values)
    except ValueError:
        _reject(
            ExtensionErrorCode.UNKNOWN_EXTENSION_POINT,
            "supported_extension_points",
            "compatibility policy includes an unknown extension point",
        )
    if set(points) != set(ExtensionPoint):
        _reject(
            ExtensionErrorCode.UNKNOWN_EXTENSION_POINT,
            "supported_extension_points",
            "SDK v1 compatibility policy must enumerate all six extension points",
        )
    provided_fingerprint = require_fingerprint(
        document["compatibility_fingerprint"], field="compatibility_fingerprint"
    )
    projection = dict(document)
    projection.pop("compatibility_fingerprint")
    if fingerprint_json(projection) != provided_fingerprint:
        _reject(
            ExtensionErrorCode.FINGERPRINT_MISMATCH,
            "compatibility_fingerprint",
            "compatibility fingerprint does not match canonical content",
        )
    sdk_api_version = SemanticVersion.parse(
        document["sdk_api_version"], field="sdk_api_version"
    )
    supported_sdk_range = _interval(
        document["supported_sdk_range"], "supported_sdk_range"
    )
    if str(sdk_api_version) != SDK_API_VERSION or (
        str(supported_sdk_range.minimum_inclusive) != SDK_API_VERSION
        or str(supported_sdk_range.maximum_exclusive) != "2.0.0"
    ):
        _reject(
            ExtensionErrorCode.INCOMPATIBLE_SDK_VERSION,
            "supported_sdk_range",
            "SDK v1 policy must lock 1.0.0 inside the [1.0.0, 2.0.0) interval",
        )
    if manifest_versions != (EXTENSION_MANIFEST_VERSION,):
        _reject(
            ExtensionErrorCode.UNSUPPORTED_MANIFEST_VERSION,
            "supported_manifest_versions",
            "SDK v1 supports exactly extension-manifest.v1",
        )
    if registry_versions != (REGISTRY_PROTOCOL_VERSION,):
        _reject(
            ExtensionErrorCode.UNSUPPORTED_REGISTRY_PROTOCOL,
            "supported_registry_protocol_versions",
            "SDK v1 supports exactly plugin-registry.v1",
        )
    return CompatibilityPolicy(
        compatibility_version=EXTENSION_COMPATIBILITY_VERSION,
        sdk_api_version=sdk_api_version,
        supported_sdk_range=supported_sdk_range,
        supported_manifest_versions=manifest_versions,
        supported_registry_protocol_versions=registry_versions,
        supported_extension_points=points,
        compatibility_fingerprint=provided_fingerprint,
    )


def resolve_manifest_set(
    manifests: tuple[ExtensionManifest, ...],
    policy: CompatibilityPolicy,
) -> RegistryResolution:
    """Validate a fixed set and return its deterministic, code-free resolution."""

    if not manifests:
        _reject(
            ExtensionErrorCode.INVALID_MANIFEST,
            "manifests",
            "resolved manifest set must not be empty",
        )
    sdk_versions = {manifest.sdk_api_version for manifest in manifests}
    if len(sdk_versions) != 1:
        _reject(
            ExtensionErrorCode.MIXED_SDK_VERSION,
            "manifests.sdk_api_version",
            "one resolved Extension set cannot mix SDK API versions",
        )
    sdk_version = next(iter(sdk_versions))
    if sdk_version != policy.sdk_api_version or not policy.supported_sdk_range.contains(
        sdk_version
    ):
        _reject(
            ExtensionErrorCode.INCOMPATIBLE_SDK_VERSION,
            "manifests.sdk_api_version",
            "resolved set is not compatible with the locked SDK version",
        )
    extension_ids = tuple(manifest.extension_id for manifest in manifests)
    if len(extension_ids) != len(set(extension_ids)):
        _reject(
            ExtensionErrorCode.DUPLICATE_EXTENSION_ID,
            "manifests.extension_id",
            "an Extension ID may resolve to only one artifact version",
        )
    contributions = tuple(
        contribution
        for manifest in manifests
        for contribution in manifest.contributions
    )
    contribution_ids = tuple(item.contribution_id for item in contributions)
    if len(contribution_ids) != len(set(contribution_ids)):
        _reject(
            ExtensionErrorCode.DUPLICATE_CONTRIBUTION_ID,
            "manifests.contributions",
            "contribution IDs must be globally unique in one resolution",
        )
    for point in (ExtensionPoint.REPLAN_POLICY, ExtensionPoint.PLUGIN_REGISTRY):
        if sum(item.extension_point is point for item in contributions) > 1:
            _reject(
                ExtensionErrorCode.REGISTRY_CONFLICT,
                f"manifests.{point.value}",
                "SDK v1 permits at most one exclusive policy contribution",
            )
    for manifest in manifests:
        if manifest.manifest_version not in policy.supported_manifest_versions:
            _reject(
                ExtensionErrorCode.UNSUPPORTED_MANIFEST_VERSION,
                manifest.extension_id,
                "manifest version is not listed by compatibility policy",
            )
        if manifest.registry_protocol_version not in policy.supported_registry_protocol_versions:
            _reject(
                ExtensionErrorCode.UNSUPPORTED_REGISTRY_PROTOCOL,
                manifest.extension_id,
                "Registry protocol is not listed by compatibility policy",
            )
        if not manifest.sdk_compatibility.contains(policy.sdk_api_version):
            _reject(
                ExtensionErrorCode.INCOMPATIBLE_SDK_VERSION,
                manifest.extension_id,
                "manifest SDK interval excludes the locked SDK version",
            )
    ordered_manifests = tuple(sorted(manifests, key=lambda item: item.extension_id))
    ordered_contributions = tuple(
        sorted(contributions, key=lambda item: (item.order, item.contribution_id))
    )
    manifest_fingerprints = tuple(
        manifest.manifest_fingerprint for manifest in ordered_manifests
    )
    projection = {
        "sdk_api_version": str(sdk_version),
        "extension_ids": [manifest.extension_id for manifest in ordered_manifests],
        "manifest_fingerprints": list(manifest_fingerprints),
        "contributions": [
            {
                "contribution_id": item.contribution_id,
                "extension_point": item.extension_point.value,
                "spi_version": item.spi_version,
                "order": item.order,
            }
            for item in ordered_contributions
        ],
    }
    return RegistryResolution(
        sdk_api_version=sdk_version,
        extension_ids=tuple(projection["extension_ids"]),
        manifest_fingerprints=manifest_fingerprints,
        contributions=ordered_contributions,
        resolution_fingerprint=fingerprint_json(projection),
    )


__all__ = [
    "EXTENSION_COMPATIBILITY_VERSION",
    "EXTENSION_MANIFEST_VERSION",
    "REGISTRY_PROTOCOL_VERSION",
    "SDK_API_VERSION",
    "CompatibilityPolicy",
    "ContributionManifest",
    "ExecutionDomain",
    "ExtensionManifest",
    "ExtensionPoint",
    "ObjectiveStage",
    "RegistryResolution",
    "parse_compatibility_policy",
    "parse_extension_manifest",
    "resolve_manifest_set",
]
