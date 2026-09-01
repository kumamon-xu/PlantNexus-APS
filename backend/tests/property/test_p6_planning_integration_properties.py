"""Deterministic properties for the P6 advisory duration projection."""

from __future__ import annotations

from copy import deepcopy

import pytest

from backend.tests.p6_planning_integration_support import (
    build_integration_problem,
    integration_inputs,
    provider_for_tests,
)


@pytest.mark.parametrize("standard_seconds", [120, 260, 600])
def test_selected_duration_is_the_only_semantic_problem_delta(
    standard_seconds: int,
) -> None:
    def mutate(document: dict[str, object]) -> None:
        records = document["records"]  # type: ignore[index]
        options = records["routing_resource_options"]  # type: ignore[index]
        options[1]["final_duration_seconds"] = standard_seconds

    snapshot, _, features = integration_inputs(mutate=mutate)
    standard = build_integration_problem(snapshot)
    accepted = build_integration_problem(
        snapshot,
        provider=provider_for_tests(),
        feature_records=features,
    )

    assert accepted.invariants.all_passed
    assert accepted.lineage[0].standard_duration_seconds == standard_seconds
    assert accepted.problem.snapshot_id == standard.problem.snapshot_id
    assert accepted.problem.problem_builder_version == (
        standard.problem.problem_builder_version
    )


def test_source_mapping_order_and_caller_mutation_do_not_change_replay() -> None:
    snapshot, key, features = integration_inputs()
    provider = provider_for_tests()
    reversed_feature = dict(reversed(list(deepcopy(features[key]).items())))

    canonical = build_integration_problem(
        snapshot, provider=provider, feature_records=features
    )
    reordered = build_integration_problem(
        snapshot,
        provider=provider,
        feature_records={key: reversed_feature},
    )

    assert reordered.problem.canonical_bytes == canonical.problem.canonical_bytes
    assert reordered.lineage[0].prediction_canonical_bytes == (
        canonical.lineage[0].prediction_canonical_bytes
    )
