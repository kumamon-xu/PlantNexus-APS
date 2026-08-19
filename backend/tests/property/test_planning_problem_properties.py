"""Fixed-seed properties for deterministic PlanningProblem replay and hashing."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any, cast

from hypothesis import given, seed, settings, strategies as st

from app.data_validation import validate_import_package
from app.domain.types import duration_to_ticks
from app.normalization.order_expansion import expand_orders
from app.planning.problem import (
    PROBLEM_BUILDER_VERSION,
    build_planning_problem,
    canonical_problem_bytes,
    problem_hash_for,
)
from app.snapshots import (
    ImmutablePlanningSnapshot,
    build_planning_snapshot,
    import_package_id_for,
)

ROOT = Path(__file__).resolve().parents[3]
CUTOFF = "2026-08-20T00:00:00Z"
HORIZON_END = "2026-08-23T00:00:00Z"


def _snapshot() -> ImmutablePlanningSnapshot:
    document = cast(
        dict[str, Any],
        json.loads(
            (ROOT / "schemas/samples/import-package.v2.synthetic.json").read_text(
                encoding="utf-8"
            )
        ),
    )
    document["package_id"] = import_package_id_for(document)
    quality = cast(dict[str, object], validate_import_package(document).document)
    expansion = expand_orders(document, quality)  # type: ignore[arg-type]
    return build_planning_snapshot(
        document,
        quality,
        expansion,
        cutoff_at_utc=CUTOFF,
    )


SNAPSHOT = _snapshot()


def _build(tick_seconds: int):  # type: ignore[no-untyped-def]
    return build_planning_problem(
        SNAPSHOT,
        problem_builder_version=PROBLEM_BUILDER_VERSION,
        tick_seconds=tick_seconds,
        horizon_start_utc=CUTOFF,
        horizon_end_utc=HORIZON_END,
    )


@seed(20260820)
@settings(max_examples=48, deadline=None)
@given(tick_seconds=st.integers(min_value=1, max_value=3600))
def test_replay_is_byte_identical_and_seconds_to_ticks_use_integer_ceiling(
    tick_seconds: int,
) -> None:
    first = _build(tick_seconds)
    second = _build(tick_seconds)

    assert first == second
    assert first.canonical_bytes == second.canonical_bytes
    assert first.problem_hash == second.problem_hash
    observed_seconds = {
        option["final_duration_seconds"]
        for operation in first.document["operation_instances"]
        for option in operation["resource_options"]
    }
    assert observed_seconds == {260, 420}
    for seconds in observed_seconds:
        ticks = duration_to_ticks(seconds, tick_seconds)
        assert ticks * tick_seconds >= seconds
        assert (ticks - 1) * tick_seconds < seconds


@seed(20260821)
@settings(max_examples=32, deadline=None)
@given(
    reverse_operations=st.booleans(),
    reverse_capabilities=st.booleans(),
    runtime_nonce=st.text(min_size=0, max_size=24),
)
def test_hash_and_canonical_bytes_ignore_collection_order_and_runtime_noise(
    reverse_operations: bool,
    reverse_capabilities: bool,
    runtime_nonce: str,
) -> None:
    baseline = _build(60)
    changed = cast(dict[str, Any], deepcopy(baseline.document))
    if reverse_operations:
        changed["operation_instances"].reverse()
        changed["precedence_edges"].reverse()
    if reverse_capabilities:
        changed["required_capabilities"].reverse()
        changed["resource_ids"].reverse()
    for operation in changed["operation_instances"]:
        operation["resource_options"].reverse()
    changed["problem_hash"] = "ignored-self-hash"
    changed["runtime_nonce"] = runtime_nonce
    changed["generated_at_utc"] = "2099-01-01T00:00:00Z"

    assert problem_hash_for(changed) == baseline.problem_hash
    changed["problem_hash"] = baseline.problem_hash
    assert canonical_problem_bytes(changed) == baseline.canonical_bytes


@seed(20260822)
@settings(max_examples=32, deadline=None)
@given(
    first_tick=st.integers(min_value=1, max_value=600),
    second_tick=st.integers(min_value=601, max_value=1200),
)
def test_distinct_explicit_tick_configs_always_change_problem_identity(
    first_tick: int,
    second_tick: int,
) -> None:
    first = _build(first_tick)
    second = _build(second_tick)

    assert first.problem_hash != second.problem_hash
    assert first.document["tick_seconds"] == first_tick
    assert second.document["tick_seconds"] == second_tick
