"""TEST-P6-PLANNING-INTEGRATION-001 contract and fail-closed evidence."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from app.duration_prediction.planning_ingress import (
    MODEL_DURATION_SOURCE,
    PlanningDurationDecision,
    PlanningDurationIngressConfig,
    PlanningDurationIngressError,
    PlanningDurationIngressErrorCode,
    build_planning_problem_with_duration_predictions,
)
from app.duration_prediction.runtime import (
    DurationCandidate,
    DurationPredictionProvider,
    DurationPredictionRequest,
    LoadedRuntimePolicy,
)
from app.planning.problem import PROBLEM_BUILDER_VERSION_V2
from scripts.p6_planning_integration_check import (
    DIFF_BASE,
    run_planning_integration_checks,
)

from backend.tests.p6_planning_integration_support import (
    CUTOFF,
    HORIZON_END,
    PREDICTED_AT,
    PRIORITY_FACTS,
    build_integration_problem,
    integration_inputs,
    provider_for_tests,
)


@dataclass(frozen=True)
class _TamperingProvider:
    policy: LoadedRuntimePolicy
    delegate: DurationPredictionProvider

    def predict(self, request: DurationPredictionRequest) -> dict[str, Any]:
        carrier = self.delegate.predict(request)
        carrier["resource_id"] = "tampered-resource"
        return carrier


def test_default_off_is_the_exact_standard_problem_and_records_lineage() -> None:
    snapshot, _, _ = integration_inputs()

    implicit = build_integration_problem(snapshot)
    explicit = build_planning_problem_with_duration_predictions(
        snapshot,
        priority_facts=PRIORITY_FACTS,
        problem_builder_version=PROBLEM_BUILDER_VERSION_V2,
        tick_seconds=60,
        horizon_start_utc=CUTOFF,
        horizon_end_utc=HORIZON_END,
        duration_ingress=PlanningDurationIngressConfig(),
    )

    assert implicit.problem is implicit.standard_problem
    assert implicit.problem.canonical_bytes == explicit.problem.canonical_bytes
    assert implicit.problem.problem_hash == explicit.problem.problem_hash
    assert implicit.invariants.all_passed
    assert [item.decision for item in implicit.lineage] == [
        PlanningDurationDecision.DEFAULT_OFF_STANDARD
    ]
    lineage = implicit.lineage[0]
    assert lineage.selected_duration_seconds == lineage.standard_duration_seconds
    assert lineage.selected_duration_source == lineage.standard_duration_source
    assert lineage.prediction_document is None


def test_accepted_and_low_confidence_paths_have_exact_selection_semantics() -> None:
    snapshot, _, features = integration_inputs()
    accepted = build_integration_problem(
        snapshot,
        provider=provider_for_tests(),
        feature_records=features,
    )
    low_confidence = build_integration_problem(
        snapshot,
        provider=provider_for_tests(
            candidate_predictor=lambda _model, _feature: DurationCandidate(
                p50_seconds=200,
                p90_seconds=300,
            )
        ),
        feature_records=features,
    )

    accepted_lineage = accepted.lineage[0]
    assert accepted_lineage.decision is PlanningDurationDecision.MODEL_CANDIDATE
    assert accepted_lineage.fallback_reason == "NONE"
    assert accepted_lineage.selected_duration_source == MODEL_DURATION_SOURCE
    assert accepted_lineage.selected_duration_seconds == 238
    assert accepted.problem.problem_hash != accepted.standard_problem.problem_hash
    assert accepted_lineage.prediction_document is not None
    assert accepted.invariants.all_passed

    fallback_lineage = low_confidence.lineage[0]
    assert fallback_lineage.decision is PlanningDurationDecision.STANDARD_FALLBACK
    assert fallback_lineage.fallback_reason == "LOW_CONFIDENCE"
    assert low_confidence.problem is low_confidence.standard_problem
    assert low_confidence.problem.canonical_bytes == accepted.standard_problem.canonical_bytes
    assert low_confidence.invariants.all_passed


def test_invalid_configuration_coverage_and_carrier_reject_before_problem_output() -> None:
    snapshot, _, features = integration_inputs()
    provider = provider_for_tests()

    with pytest.raises(PlanningDurationIngressError) as missing_provider:
        build_planning_problem_with_duration_predictions(
            snapshot,
            priority_facts=PRIORITY_FACTS,
            problem_builder_version=PROBLEM_BUILDER_VERSION_V2,
            tick_seconds=60,
            horizon_start_utc=CUTOFF,
            horizon_end_utc=HORIZON_END,
            duration_ingress=PlanningDurationIngressConfig(
                enabled=True,
                predicted_at_utc=PREDICTED_AT,
                feature_records=features,
            ),
        )
    assert missing_provider.value.code is (
        PlanningDurationIngressErrorCode.INVALID_CONFIGURATION
    )

    with pytest.raises(PlanningDurationIngressError) as missing_feature:
        build_integration_problem(
            snapshot,
            provider=provider,
            feature_records={},
        )
    assert missing_feature.value.code is (
        PlanningDurationIngressErrorCode.FEATURE_COVERAGE_MISMATCH
    )

    with pytest.raises(PlanningDurationIngressError) as tampered_carrier:
        build_integration_problem(
            snapshot,
            provider=_TamperingProvider(provider.policy, provider),  # type: ignore[arg-type]
            feature_records=features,
        )
    assert tampered_carrier.value.code is (
        PlanningDurationIngressErrorCode.PREDICTION_CONTRACT_INVALID
    )


def test_inputs_and_returned_carrier_copies_cannot_poison_replay() -> None:
    snapshot, _, features = integration_inputs()
    original_features = deepcopy(features)
    provider = provider_for_tests()

    first = build_integration_problem(
        snapshot, provider=provider, feature_records=features
    )
    carrier = first.lineage[0].prediction_document
    assert carrier is not None
    carrier["selected_duration_seconds"] = 1
    features[next(iter(features))]["features"].reverse()

    second = build_integration_problem(
        snapshot, provider=provider, feature_records=original_features
    )
    assert second.problem.canonical_bytes == first.problem.canonical_bytes
    assert second.lineage[0].prediction_canonical_bytes == (
        first.lineage[0].prediction_canonical_bytes
    )
    assert original_features != features


def test_machine_report_contract_executes_all_non_skippable_integration_checks() -> None:
    root = Path(__file__).resolve().parents[3]
    report = run_planning_integration_checks(root)

    assert report["status"] == "PASS"
    assert report["task_id"] == "TASK-P6-07"
    assert report["diff_base"] == DIFF_BASE
    assert report["check_count"] == 11
    assert report["counts"] == {
        "ingress_paths": 5,
        "authority_invariants": 7,
        "authority_mutations": 5,
        "fresh_validator_passes": 3,
        "formal_validator_mutations": 2,
        "preserved_owner_files": 16,
    }
    assert report["issues"] == []
