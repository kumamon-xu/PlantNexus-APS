from __future__ import annotations

from collections import Counter
from dataclasses import replace
from types import MappingProxyType

import pytest

from plantnexus_demo import DemoIngressPipeline, DemoPackageGenerator
from plantnexus_demo.ingress import problem_counts


@pytest.mark.parametrize("profile_name", ["smoke", "showcase", "upper"])
def test_every_profile_uses_the_complete_standard_ingress(profile_name: str) -> None:
    generated = DemoPackageGenerator().prepare_batch(profile_name)
    artifacts = DemoIngressPipeline().run(generated)
    profile = generated.profile
    counts = problem_counts(artifacts)

    assert artifacts.normalization.document["import_package_version"] == "import-package.v2"
    assert artifacts.quality.document["status"] == "PASS"
    assert artifacts.expansion.document["expansion_version"] == "order-expansion.v1"
    assert artifacts.snapshot.document["snapshot_version"] == "planning-snapshot.v2"
    assert artifacts.problem.document["problem_version"] == "planning-problem.v2"
    assert counts["orders"] == profile.order_count
    assert counts["active_operations"] == profile.active_operation_count
    assert counts["running_operations"] == profile.running_operation_count
    assert counts["resources"] == profile.resource_count
    assert counts["hard_locks"] == profile.hard_lock_count
    assert counts["soft_locks"] == profile.soft_lock_count

    expansion_statuses = Counter(
        operation["status"]
        for operation in artifacts.expansion.document["operation_instances"]
    )
    assert expansion_statuses["COMPLETED"] == profile.completed_operation_count
    assert expansion_statuses["RUNNING"] == profile.running_operation_count


def test_showcase_priority_weights_are_explicit_and_versioned() -> None:
    artifacts = DemoIngressPipeline().run(
        DemoPackageGenerator().prepare_batch("showcase")
    )
    weights = Counter(
        demand["priority_weight"]
        for demand in artifacts.problem.document["delivery_demands"]
    )
    assert weights == Counter({1: 96, 4: 29, 12: 7})
    assert {
        demand["priority_source_system"]
        for demand in artifacts.problem.document["delivery_demands"]
    } == {"plantnexus-synthetic-policy"}


def test_missing_priority_fact_fails_closed() -> None:
    generated = DemoPackageGenerator().prepare_batch("smoke")
    corrupted = replace(
        generated,
        priority_class_by_demand_source_id=MappingProxyType({}),
    )
    with pytest.raises(ValueError, match="explicit demo priority fact"):
        DemoIngressPipeline().run(corrupted)
