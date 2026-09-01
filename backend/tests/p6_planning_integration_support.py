"""Shared synthetic builders for TASK-P6-07 integration and invariant tests."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
import json
from pathlib import Path
from typing import Any, cast

from app.data_validation import validate_import_package
from app.duration_prediction.planning_ingress import (
    DurationOptionKey,
    PlanningDurationIngressConfig,
    PlanningDurationIngressResult,
    build_planning_problem_with_duration_predictions,
    standard_duration_authority_for_snapshot_option,
)
from app.duration_prediction.runtime import (
    CandidatePredictor,
    DurationPredictionProvider,
    MonotonicClock,
)
from app.normalization.order_expansion import expand_orders
from app.planning.policy import simulation_delivery_policy, simulation_solve_limits
from app.planning.problem import PROBLEM_BUILDER_VERSION_V2
from app.planning.strategies import GlobalCpSatStrategy
from app.planning.strategies.global_cp_sat import GlobalStrategyResult
from app.snapshots import (
    ImmutablePlanningSnapshot,
    build_planning_snapshot,
    import_package_id_for,
)

from backend.tests.p6_duration_runtime_support import (
    DATASET_PATH,
    build_test_provider,
    load_json,
    recompute_feature_identity,
)


ROOT = Path(__file__).resolve().parents[2]
CUTOFF = "2026-08-20T00:00:00Z"
HORIZON_END = "2026-08-21T00:00:00Z"
PREDICTED_AT = "2026-09-01T10:30:00Z"
FACTORY_ID = "factory-sim-p6-001"
RESOURCE_ID = "resource-sim-p6-2"
OPTION_IDS = ("resource-option-sim-p6-1", "resource-option-sim-p6-2")
PRIORITY_FACTS: dict[str, Mapping[str, object]] = {
    "DEMAND-001": {
        "priority_weight": 2,
        "source_system": "plantnexus-synthetic-policy",
        "source_version": "1.0.0",
        "source_record_id": "SIM-P2-DELIVERY-PRIORITY-001",
    }
}


def _prepare_v2_document(document: dict[str, Any]) -> None:
    records = document["records"]
    old_factory = records["factories"][0]["factory_id"]
    records["factories"][0]["factory_id"] = FACTORY_ID
    for workshop in records["workshops"]:
        if workshop["factory_id"] == old_factory:
            workshop["factory_id"] = FACTORY_ID

    old_resource = records["resources"][0]["resource_id"]
    records["resources"][0]["resource_id"] = RESOURCE_ID
    for index, option in enumerate(records["routing_resource_options"]):
        if option["resource_id"] == old_resource:
            option["resource_id"] = RESOURCE_ID
        option["routing_resource_option_id"] = OPTION_IDS[index]
    for fact in records["execution_facts"]:
        if fact["resource_id"] == old_resource:
            fact["resource_id"] = RESOURCE_ID
    for lock in records["operation_locks"]:
        if lock["resource_id"] == old_resource:
            lock["resource_id"] = RESOURCE_ID

    fact = records["execution_facts"][0]
    fact["status"] = "COMPLETED"
    fact.pop("remaining_quantity")
    fact.pop("remaining_seconds")
    fact["actual_end_at_utc"] = "2026-08-19T00:05:00Z"
    fact["completed_quantity"] = 10

    records["routing_precedence_edges"] = []
    records["operation_locks"] = []


def integration_snapshot(
    mutate: Callable[[dict[str, Any]], None] | None = None,
) -> ImmutablePlanningSnapshot:
    document = cast(
        dict[str, Any],
        json.loads(
            (ROOT / "schemas/samples/import-package.v2.synthetic.json").read_text(
                encoding="utf-8"
            )
        ),
    )
    _prepare_v2_document(document)
    if mutate is not None:
        mutate(document)
    document["package_id"] = import_package_id_for(document)
    quality = cast(dict[str, object], validate_import_package(document).document)
    expansion = expand_orders(document, quality)  # type: ignore[arg-type]
    return build_planning_snapshot(
        document,
        quality,
        expansion,
        cutoff_at_utc=CUTOFF,
    )


def active_option_key(snapshot: ImmutablePlanningSnapshot) -> DurationOptionKey:
    active = [
        instance
        for instance in snapshot.document["operation_instances"]
        if instance["status"] == "NOT_STARTED"
    ]
    assert len(active) == 1
    options = active[0]["resource_options"]
    assert len(options) == 1
    return DurationOptionKey(
        operation_id=active[0]["operation_instance_id"],
        resource_option_id=options[0]["routing_resource_option_id"],
        resource_id=options[0]["resource_id"],
    )


def feature_for_snapshot_option(
    snapshot: ImmutablePlanningSnapshot, key: DurationOptionKey
) -> dict[str, Any]:
    dataset = load_json(DATASET_PATH)
    row = next(
        item
        for item in dataset["rows"]
        if item["feature_record"]["resource_id"] == RESOURCE_ID
    )
    feature = deepcopy(row["feature_record"])
    authority = standard_duration_authority_for_snapshot_option(snapshot, key)
    instance = next(
        value
        for value in snapshot.document["operation_instances"]
        if value["operation_instance_id"] == key.operation_id
    )
    option = next(
        value
        for value in instance["resource_options"]
        if value["routing_resource_option_id"] == key.resource_option_id
    )
    feature.update(
        {
            "factory_id": FACTORY_ID,
            "operation_id": key.operation_id,
            "resource_option_id": key.resource_option_id,
            "resource_id": key.resource_id,
            "as_of_cutoff_utc": CUTOFF,
        }
    )
    source = feature["source_records"][0]
    source.update(
        {
            "source_system": authority["duration_source"],
            "source_version": authority["source_version"],
            "source_record_id": authority["source_record_id"],
            "record_fingerprint": authority["source_record_fingerprint"],
        }
    )
    for value in feature["features"]:
        value["source_record_ids"] = [authority["source_record_id"]]
        if value["feature_name"] == "standard_duration_seconds":
            value["value"] = authority["seconds"]
        elif value["feature_name"] == "setup_seconds":
            value["value"] = option["setup_seconds"]
        elif value["feature_name"] == "planned_quantity":
            value["value"] = instance["quantity"]
        elif value["feature_name"] == "operation_family":
            value["value"] = "turning"
    return recompute_feature_identity(feature)


def integration_inputs(
    *,
    mutate: Callable[[dict[str, Any]], None] | None = None,
) -> tuple[
    ImmutablePlanningSnapshot,
    DurationOptionKey,
    dict[DurationOptionKey, dict[str, Any]],
]:
    snapshot = integration_snapshot(mutate)
    key = active_option_key(snapshot)
    return snapshot, key, {key: feature_for_snapshot_option(snapshot, key)}


def provider_for_tests(
    *,
    candidate_predictor: CandidatePredictor | None = None,
    monotonic_clock: MonotonicClock | None = None,
) -> DurationPredictionProvider:
    return build_test_provider(
        candidate_predictor=candidate_predictor,
        monotonic_clock=monotonic_clock,
    )


def build_integration_problem(
    snapshot: ImmutablePlanningSnapshot,
    *,
    provider: DurationPredictionProvider | None = None,
    feature_records: Mapping[DurationOptionKey, Mapping[str, Any]] | None = None,
) -> PlanningDurationIngressResult:
    config = None
    if provider is not None:
        assert feature_records is not None
        config = PlanningDurationIngressConfig.enabled_for_simulation(
            provider=provider,
            predicted_at_utc=PREDICTED_AT,
            feature_records=feature_records,
        )
    return build_planning_problem_with_duration_predictions(
        snapshot,
        priority_facts=PRIORITY_FACTS,
        problem_builder_version=PROBLEM_BUILDER_VERSION_V2,
        tick_seconds=60,
        horizon_start_utc=CUTOFF,
        horizon_end_utc=HORIZON_END,
        duration_ingress=config,
    )


def solve_problem(
    result: PlanningDurationIngressResult, *, run_id: str
) -> GlobalStrategyResult:
    limits = simulation_solve_limits(
        limits_id=f"LIMITS-{run_id}",
        limits_revision="1.0.0",
        source_record_id=f"SOURCE-{run_id}",
        max_wall_time_seconds=5.0,
        max_workers=1,
        random_seed=20260901,
    )
    return GlobalCpSatStrategy().solve(
        result.problem.document,
        simulation_delivery_policy(),
        limits,
        planning_run_id=run_id,
        code_commit="uncommitted",
    )


__all__ = [
    "CUTOFF",
    "FACTORY_ID",
    "HORIZON_END",
    "OPTION_IDS",
    "PREDICTED_AT",
    "PRIORITY_FACTS",
    "RESOURCE_ID",
    "active_option_key",
    "build_integration_problem",
    "feature_for_snapshot_option",
    "integration_inputs",
    "integration_snapshot",
    "provider_for_tests",
    "solve_problem",
]
