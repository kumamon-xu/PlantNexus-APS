"""P6 standard/fallback/accepted Problem→Solver→fresh Validator integration."""

from __future__ import annotations

from copy import deepcopy
from collections.abc import Mapping
from typing import Any, cast

from app.duration_prediction.runtime import DurationCandidate, DurationProviderSignal
from app.planning.validation import validate_problem_schedule

from backend.tests.p6_planning_integration_support import (
    build_integration_problem,
    integration_inputs,
    provider_for_tests,
    solve_problem,
)


def _constraint_ids(report: Mapping[str, Any]) -> set[str]:
    return {
        cast(str, value["constraint_id"])
        for value in cast(list[dict[str, Any]], report["violations"])
    }


def test_three_ingress_paths_replay_and_pass_fresh_formal_validator() -> None:
    snapshot, _, features = integration_inputs()
    standard = build_integration_problem(snapshot)
    fallback = build_integration_problem(
        snapshot,
        provider=provider_for_tests(
            candidate_predictor=lambda _model, _feature: (_ for _ in ()).throw(
                DurationProviderSignal("PROVIDER_UNAVAILABLE")
            )
        ),
        feature_records=features,
    )
    accepted = build_integration_problem(
        snapshot,
        provider=provider_for_tests(),
        feature_records=features,
    )

    assert fallback.problem.canonical_bytes == standard.problem.canonical_bytes
    assert fallback.lineage[0].fallback_reason == "PROVIDER_UNAVAILABLE"
    assert accepted.problem.problem_hash != standard.problem.problem_hash
    assert all(
        result.invariants.all_passed for result in (standard, fallback, accepted)
    )

    for index, result in enumerate((standard, fallback, accepted), start=1):
        solved = solve_problem(result, run_id=f"RUN-P6-07-INTEGRATION-{index}")
        assert solved.solution["solver_status"] == "OPTIMAL"
        assert solved.validation_report is not None
        assert solved.validation_report["status"] == "PASS"
        fresh = validate_problem_schedule(result.problem.document, solved.solution)
        assert fresh == solved.validation_report


def test_accepted_problem_replays_byte_exactly_for_same_explicit_inputs() -> None:
    snapshot, _, features = integration_inputs()
    provider = provider_for_tests()

    first = build_integration_problem(
        snapshot, provider=provider, feature_records=features
    )
    second = build_integration_problem(
        snapshot, provider=provider, feature_records=features
    )

    assert first.problem.canonical_bytes == second.problem.canonical_bytes
    assert first.lineage_documents() == second.lineage_documents()
    assert first.standard_problem.canonical_bytes == second.standard_problem.canonical_bytes


def test_fresh_validator_rejects_wrong_resource_and_standard_duration_replay() -> None:
    snapshot, _, features = integration_inputs()
    accepted = build_integration_problem(
        snapshot,
        provider=provider_for_tests(),
        feature_records=features,
    )
    solved = solve_problem(accepted, run_id="RUN-P6-07-MUTATION-SOURCE")
    assert solved.validation_report is not None

    wrong_resource = deepcopy(solved.solution)
    wrong_resource["assignments"][0]["resource_id"] = "not-a-candidate-resource"
    resource_report = validate_problem_schedule(
        accepted.problem.document, wrong_resource
    )
    assert resource_report["status"] == "FAIL"
    assert "C-003" in _constraint_ids(resource_report)

    wrong_duration = deepcopy(solved.solution)
    wrong_duration["assignments"][0]["duration_seconds"] = (
        accepted.lineage[0].standard_duration_seconds
    )
    duration_report = validate_problem_schedule(
        accepted.problem.document, wrong_duration
    )
    assert duration_report["status"] == "FAIL"
    assert "C-010" in _constraint_ids(duration_report)


def test_invalid_quantile_provider_becomes_exact_standard_fallback() -> None:
    snapshot, _, features = integration_inputs()
    result = build_integration_problem(
        snapshot,
        provider=provider_for_tests(
            candidate_predictor=lambda _model, _feature: DurationCandidate(
                p50_seconds=300,
                p90_seconds=200,
            )
        ),
        feature_records=features,
    )
    assert result.lineage[0].fallback_reason == "INVALID_QUANTILES"
    assert result.problem is result.standard_problem
