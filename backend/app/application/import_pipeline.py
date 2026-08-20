"""Application orchestration for the P1 staging-to-Problem ingress chain."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import cast

from app.data_validation import DataValidationResult, validate_import_package
from app.domain.canonical_records import ImportPackageDocumentV2
from app.domain.contracts import ErrorDocumentV3
from app.domain.production import OrderExpansionResult
from app.importers import (
    ImportStagingError,
    StagingDataPlane,
    StagingErrorCode,
)
from app.normalization import (
    NormalizationInput,
    NormalizationResult,
    UnitConversionRegistry,
    expand_orders,
    normalize_import,
)
from app.planning.problem import (
    ImmutablePlanningProblem,
    build_planning_problem,
)
from app.snapshots import ImmutablePlanningSnapshot, build_planning_snapshot


@dataclass(frozen=True, slots=True)
class PlanningBuildConfiguration:
    """Explicit data-plane and time discretization selected by the caller."""

    expected_data_plane: StagingDataPlane
    cutoff_at_utc: str
    horizon_end_utc: str
    tick_seconds: int
    problem_builder_version: str


class DataQualityGateRejected(ValueError):
    """Preserve the exact first canonical quality error and the complete report."""

    stage = "data_validation"

    def __init__(self, result: DataValidationResult) -> None:
        errors = tuple(result.document["errors"])
        if not errors:
            raise ValueError("a rejected quality gate requires at least one error")
        first = cast(ErrorDocumentV3, errors[0])
        self.result = result
        self.report = result.document
        self.errors = errors
        self.category = first["category"]
        self.code = first["code"]
        self.message = first["message"]
        super().__init__(
            f"{self.category}/{self.code} at {self.stage}: {self.message}"
        )


@dataclass(frozen=True, slots=True)
class CommonIngressArtifacts:
    """Successful immutable handoff values from each public P1 boundary."""

    normalization: NormalizationResult
    quality: DataValidationResult
    expansion: OrderExpansionResult
    snapshot: ImmutablePlanningSnapshot
    problem: ImmutablePlanningProblem


@dataclass(frozen=True, slots=True)
class CommonIngressPipeline:
    """Compose existing public boundaries without copying their business rules."""

    unit_registry: UnitConversionRegistry

    def run(
        self,
        inputs: Sequence[NormalizationInput],
        *,
        configuration: PlanningBuildConfiguration,
    ) -> CommonIngressArtifacts:
        normalized_inputs = tuple(inputs)
        for item in normalized_inputs:
            if item.batch.data_plane is not configuration.expected_data_plane:
                raise ImportStagingError(
                    StagingErrorCode.DATA_PLANE_MISMATCH,
                    "staged input does not match the selected application data plane",
                )

        normalization = normalize_import(
            normalized_inputs,
            unit_registry=self.unit_registry,
        )
        import_document = cast(ImportPackageDocumentV2, normalization.document)
        quality = validate_import_package(import_document)
        if not quality.passed:
            raise DataQualityGateRejected(quality)
        expansion = expand_orders(import_document, quality.document)
        snapshot = build_planning_snapshot(
            import_document,
            quality.document,
            expansion,
            cutoff_at_utc=configuration.cutoff_at_utc,
        )
        problem = build_planning_problem(
            snapshot,
            problem_builder_version=configuration.problem_builder_version,
            tick_seconds=configuration.tick_seconds,
            horizon_start_utc=configuration.cutoff_at_utc,
            horizon_end_utc=configuration.horizon_end_utc,
        )
        return CommonIngressArtifacts(
            normalization=normalization,
            quality=quality,
            expansion=expansion,
            snapshot=snapshot,
            problem=problem,
        )


__all__ = [
    "CommonIngressArtifacts",
    "CommonIngressPipeline",
    "DataQualityGateRejected",
    "PlanningBuildConfiguration",
]
