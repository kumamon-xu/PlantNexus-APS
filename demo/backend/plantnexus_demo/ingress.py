"""Demo orchestration over the repository's public import-to-Problem boundaries."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
import sys
from types import MappingProxyType
from typing import Any, ContextManager, cast

import yaml

from app.application.import_pipeline import DataQualityGateRejected
from app.data_validation import DataValidationResult, validate_import_package
from app.domain.canonical_records import ImportPackageDocumentV2
from app.domain.production import OrderExpansionResult
from app.normalization import (
    NormalizationInput,
    NormalizationResult,
    UnitConversionRegistry,
    expand_orders,
    normalize_import,
)
from app.planning.problem import (
    ImmutablePlanningProblemV2,
    PROBLEM_BUILDER_VERSION_V2,
    build_planning_problem_v2,
)
from app.snapshots import ImmutablePlanningSnapshot, build_planning_snapshot

from .generator import DemoGeneratedBatch


@dataclass(frozen=True, slots=True)
class DemoIngressArtifacts:
    generated: DemoGeneratedBatch
    normalization: NormalizationResult
    quality: DataValidationResult
    expansion: OrderExpansionResult
    snapshot: ImmutablePlanningSnapshot
    problem: ImmutablePlanningProblemV2
    priority_facts: Mapping[str, Mapping[str, object]]


def load_unit_registry(repository_root: Path | None = None) -> UnitConversionRegistry:
    bundled_root = getattr(sys, "_MEIPASS", None)
    root = (
        Path(bundled_root) / "repository"
        if repository_root is None and bundled_root is not None
        else Path(__file__).resolve().parents[3]
        if repository_root is None
        else repository_root
    )
    registry_path = root / "schemas" / "rules" / "unit-conversion-registry.v1.yaml"
    try:
        raw = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as error:
        raise ValueError("the repository unit-conversion registry is unavailable") from error
    if not isinstance(raw, Mapping):
        raise ValueError("the repository unit-conversion registry must be an object")
    return UnitConversionRegistry.from_mapping(raw)


def _priority_facts(
    generated: DemoGeneratedBatch,
    import_document: ImportPackageDocumentV2,
) -> Mapping[str, Mapping[str, object]]:
    policy = generated_priority_policy(generated)
    classes = {
        str(item["class_id"]): item
        for item in policy["classes"]
    }
    facts: dict[str, Mapping[str, object]] = {}
    for demand in import_document["records"]["demand_orders"]:
        source_id = str(demand["source"]["source_record_id"])
        try:
            class_id = generated.priority_class_by_demand_source_id[source_id]
            priority_class = classes[class_id]
        except KeyError as error:
            raise ValueError("every canonical demand needs one explicit demo priority fact") from error
        demand_id = str(demand["demand_order_id"])
        facts[demand_id] = MappingProxyType(
            {
                "priority_weight": int(priority_class["priority_weight"]),
                "source_system": str(policy["source_system"]),
                "source_version": str(policy["source_version"]),
                "source_record_id": f"priority:{source_id}:{class_id}",
            }
        )
    return MappingProxyType(facts)


def generated_priority_policy(generated: DemoGeneratedBatch) -> Mapping[str, Any]:
    """Resolve the already-validated priority policy without mutable global state."""

    from .assets import load_demo_assets

    assets = load_demo_assets()
    if assets.asset_digest != generated.assets_digest:
        raise ValueError("demo assets changed after the batch was generated")
    return assets.priority_policy


class DemoIngressPipeline:
    """Run Standard Import, quality, expansion, Snapshot, and v2 Problem."""

    def __init__(self, unit_registry: UnitConversionRegistry | None = None) -> None:
        self.unit_registry = load_unit_registry() if unit_registry is None else unit_registry

    def run(
        self,
        generated: DemoGeneratedBatch,
        *,
        stage_context: Callable[[str], ContextManager[None]] | None = None,
    ) -> DemoIngressArtifacts:
        stage = nullcontext if stage_context is None else stage_context
        with stage("NORMALIZING"):
            normalization = normalize_import(
                (NormalizationInput(generated.batch, generated.mapping_profile),),
                unit_registry=self.unit_registry,
            )
        import_document = cast(ImportPackageDocumentV2, normalization.document)
        with stage("VALIDATING_DATA"):
            quality = validate_import_package(import_document)
            if not quality.passed:
                raise DataQualityGateRejected(quality)
            expansion = expand_orders(import_document, quality.document)
        with stage("SNAPSHOTTING"):
            snapshot = build_planning_snapshot(
                import_document,
                quality.document,
                expansion,
                cutoff_at_utc=generated.profile.anchor_at_utc,
            )
        with stage("BUILDING_PROBLEM"):
            priorities = _priority_facts(generated, import_document)
            horizon_end = (
                _parse_anchor(generated.profile.anchor_at_utc)
                + timedelta(days=generated.profile.horizon_days)
            )
            problem = build_planning_problem_v2(
                snapshot,
                priority_facts=priorities,
                problem_builder_version=PROBLEM_BUILDER_VERSION_V2,
                tick_seconds=300,
                horizon_start_utc=generated.profile.anchor_at_utc,
                horizon_end_utc=horizon_end.isoformat().replace("+00:00", "Z"),
            )
        return DemoIngressArtifacts(
            generated=generated,
            normalization=normalization,
            quality=quality,
            expansion=expansion,
            snapshot=snapshot,
            problem=problem,
            priority_facts=priorities,
        )


def _parse_anchor(value: str):
    from datetime import UTC, datetime

    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def problem_counts(artifacts: DemoIngressArtifacts) -> dict[str, int]:
    document = artifacts.problem.document
    status_counts = {"RUNNING": 0, "NOT_STARTED": 0}
    for operation in document["operation_instances"]:
        status_counts[str(operation["status"])] += 1
    return {
        "orders": len(document["delivery_demands"]),
        "active_operations": len(document["operation_instances"]),
        "running_operations": status_counts["RUNNING"],
        "not_started_operations": status_counts["NOT_STARTED"],
        "completed_anchors": len(document["historical_completion_anchors"]),
        "resources": len(document["resources"]),
        "resource_options": sum(
            len(operation["resource_options"])
            for operation in document["operation_instances"]
        ),
        "hard_locks": sum(
            lock["lock_type"] == "HARD_LOCK" for lock in document["operation_locks"]
        ),
        "soft_locks": sum(
            lock["lock_type"] == "SOFT_LOCK" for lock in document["operation_locks"]
        ),
        "unavailable_intervals": len(document["resource_unavailable_intervals"]),
    }


__all__ = [
    "DemoIngressArtifacts",
    "DemoIngressPipeline",
    "generated_priority_policy",
    "load_unit_registry",
    "problem_counts",
]
