from __future__ import annotations

from collections import Counter, defaultdict

import pytest

from app.importers import StagedImportBatch, StagingDataPlane
from plantnexus_demo.generator import DemoPackageGenerator


@pytest.mark.parametrize("profile_name", ["smoke", "showcase", "upper"])
def test_generator_is_byte_deterministic(profile_name: str) -> None:
    generator = DemoPackageGenerator()
    first = generator.prepare_batch(profile_name)
    second = generator.prepare_batch(profile_name)

    assert first.batch.request_fingerprint == second.batch.request_fingerprint
    assert first.batch.content_sha256 == second.batch.content_sha256
    assert tuple(row.raw_payload for row in first.batch.rows) == tuple(
        row.raw_payload for row in second.batch.rows
    )
    assert isinstance(first.batch, StagedImportBatch)
    assert first.batch.data_plane is StagingDataPlane.SIMULATION


@pytest.mark.parametrize("profile_name", ["showcase", "upper"])
def test_generated_scale_matches_every_declared_quota(profile_name: str) -> None:
    generated = DemoPackageGenerator().prepare_batch(profile_name)
    profile = generated.profile
    records = generated.records

    assert len(records["demand_orders"]) == profile.order_count
    assert len(records["routing_operations"]) == profile.operation_count
    assert len(records["resources"]) == profile.resource_count
    assert len(records["routing_resource_options"]) == sum(
        count * candidates
        for candidates, count in profile.candidate_count_targets.items()
    )

    options_by_operation: dict[str, int] = defaultdict(int)
    for option in records["routing_resource_options"]:
        options_by_operation[str(option["routing_operation_id"])] += 1
    assert Counter(options_by_operation.values()) == Counter(
        {count: operations for count, operations in profile.candidate_count_targets.items()}
    )
    assert Counter(
        fact["status"] for fact in records["execution_facts"]
    ) == Counter(
        {
            "COMPLETED": profile.completed_operation_count,
            "RUNNING": profile.running_operation_count,
        }
    )
    assert Counter(
        lock["lock_type"] for lock in records["operation_locks"]
    ) == Counter(
        {"HARD_LOCK": profile.hard_lock_count, "SOFT_LOCK": profile.soft_lock_count}
    )
    assert Counter(generated.priority_class_by_demand_source_id.values()) == Counter(
        profile.priority_class_counts
    )


def test_showcase_has_the_documented_1311_resource_options() -> None:
    generated = DemoPackageGenerator().prepare_batch("showcase")
    assert len(generated.records["routing_resource_options"]) == 1_311
    assert len(generated.records["execution_facts"]) == 42
    assert len(generated.records["operation_locks"]) == 12
