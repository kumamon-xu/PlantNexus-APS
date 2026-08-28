"""TASK-P4-08 deterministic projection and identity properties."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from typing import cast

from hypothesis import given, settings, strategies as st

from app.application.replan_application_check import (
    build_replan_application_fixture,
)
from app.domain.execution_contracts import canonical_contract_bytes
from app.domain.replan_application import schedule_content, schedule_identity
from app.planning.problem.freeze_projection import project_effective_locks
from app.planning.problem.freeze_window_check import build_freeze_window_fixture


ROOT = Path(__file__).resolve().parents[3]
FROZEN = build_freeze_window_fixture(ROOT)
PROJECTION = project_effective_locks(
    snapshot=FROZEN.snapshot,
    problem=FROZEN.problem,
    base_schedule=FROZEN.base_schedule,
    policy=FROZEN.policy,
).document


@settings(max_examples=8, deadline=None)
@given(
    reverse_assignments=st.booleans(),
    reverse_hard=st.booleans(),
    reverse_soft=st.booleans(),
)
def test_schedule_projection_is_order_invariant_and_does_not_mutate_inputs(
    reverse_assignments: bool,
    reverse_hard: bool,
    reverse_soft: bool,
) -> None:
    assignments = deepcopy(FROZEN.base_schedule["content"]["assignments"])  # type: ignore[index]
    candidate = {
        "assignments": (
            list(reversed(assignments)) if reverse_assignments else assignments
        )
    }
    projection = deepcopy(PROJECTION)
    if reverse_hard:
        projection["explicit_hard_locks"] = list(
            reversed(cast(list[object], projection["explicit_hard_locks"]))
        )
        projection["freeze_derived_hard_locks"] = list(
            reversed(cast(list[object], projection["freeze_derived_hard_locks"]))
        )
    if reverse_soft:
        projection["soft_locks"] = list(
            reversed(cast(list[object], projection["soft_locks"]))
        )
    candidate_before = canonical_contract_bytes(candidate)
    projection_before = canonical_contract_bytes(projection)

    observed = schedule_content(
        candidate=candidate,
        effective_locks=projection,
    )
    canonical = schedule_content(
        candidate={"assignments": assignments},
        effective_locks=PROJECTION,
    )
    assert observed == canonical
    assert canonical_contract_bytes(candidate) == candidate_before
    assert canonical_contract_bytes(projection) == projection_before


@settings(max_examples=12, deadline=None)
@given(key=st.text(alphabet="0123456789abcdef", min_size=64, max_size=64))
def test_schedule_identity_is_total_deterministic_and_key_bound(key: str) -> None:
    fixture = build_replan_application_fixture(ROOT)
    context = replace(
        fixture.context,
        idempotency_key_reference="sha256:" + key,
    )
    fingerprint = cast(str, fixture.request["request_fingerprint"])
    first = schedule_identity(request_fingerprint=fingerprint, context=context)
    second = schedule_identity(request_fingerprint=fingerprint, context=context)
    assert first == second
    assert len(first) == len("schedule-version-replan-") + 64
