"""TASK-P4-08 pure authorization, identity, and carrier projection tests."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest

from app.application.replan_application_check import (
    build_replan_application_fixture,
)
from app.domain.execution_contracts import replan_request_fingerprint
from app.domain.replan_application import (
    ReplanApplicationError,
    ReplanApplicationFailure,
    require_replan_application_authorization,
    require_replan_request_context,
    schedule_content,
    schedule_identity,
)
from app.planning.problem.freeze_projection import project_effective_locks
from app.planning.problem.freeze_window_check import build_freeze_window_fixture


ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"data_plane": "PRODUCTION"}, "data_plane/environment/production_binding"),
        ({"environment": "PRODUCTION"}, "data_plane/environment/production_binding"),
        ({"production_binding": True}, "data_plane/environment/production_binding"),
        ({"actor_ref": "anonymous"}, "actor_ref"),
    ],
)
def test_application_authority_is_simulation_only_and_default_deny(
    changes: dict[str, object], field: str
) -> None:
    context = build_replan_application_fixture(ROOT).context
    denied = replace(context, **changes)
    with pytest.raises(ReplanApplicationError) as captured:
        require_replan_application_authorization(denied)
    assert captured.value.reason is ReplanApplicationFailure.AUTHORIZATION_DENIED
    assert captured.value.field == field


def test_request_context_is_exact_and_cannot_self_grant_authority() -> None:
    fixture = build_replan_application_fixture(ROOT)
    require_replan_request_context(fixture.request, fixture.context)

    changed = deepcopy(fixture.request)
    changed["correlation_id"] = "different-correlation"
    changed["request_fingerprint"] = replan_request_fingerprint(changed)
    changed["request_id"] = "replan-request-" + cast(
        str, changed["request_fingerprint"]
    ).removeprefix("sha256:")
    with pytest.raises(ReplanApplicationError) as captured:
        require_replan_request_context(changed, fixture.context)
    assert captured.value.reason is ReplanApplicationFailure.LINEAGE_MISMATCH
    assert captured.value.field == "replan_request.correlation_id"


def test_schedule_identity_binds_request_attempt_and_idempotency_key() -> None:
    fixture = build_replan_application_fixture(ROOT)
    first = schedule_identity(
        request_fingerprint=fixture.request["request_fingerprint"],  # type: ignore[arg-type]
        context=fixture.context,
    )
    assert first == schedule_identity(
        request_fingerprint=fixture.request["request_fingerprint"],  # type: ignore[arg-type]
        context=fixture.context,
    )
    changed = schedule_identity(
        request_fingerprint=fixture.request["request_fingerprint"],  # type: ignore[arg-type]
        context=replace(
            fixture.context,
            idempotency_key_reference=(
                "sha256:" + "f" * 64
            ),
        ),
    )
    assert changed != first
    assert first.startswith("schedule-version-replan-")


def test_schedule_content_is_sorted_and_uses_tick_occupied_duration() -> None:
    frozen = build_freeze_window_fixture(ROOT)
    projection = project_effective_locks(
        snapshot=frozen.snapshot,
        problem=frozen.problem,
        base_schedule=frozen.base_schedule,
        policy=frozen.policy,
    ).document
    assignments = deepcopy(frozen.base_schedule["content"]["assignments"])  # type: ignore[index]
    assignments[1]["duration_seconds"] = 260
    candidate = {"assignments": list(reversed(assignments))}

    first = schedule_content(candidate=candidate, effective_locks=projection)
    replay = schedule_content(candidate=candidate, effective_locks=projection)
    projected_assignments = cast(list[dict[str, object]], first["assignments"])
    projected_locks = cast(list[dict[str, object]], first["locks"])
    assert first == replay
    operation_ids = [
        cast(str, item["operation_id"]) for item in projected_assignments
    ]
    assert operation_ids == sorted(operation_ids)
    second = next(
        item
        for item in projected_assignments
        if item["operation_id"] == frozen.second_operation_id
    )
    assert second["duration_seconds"] == 300
    assert {item["lock_type"] for item in projected_locks} == {"HARD", "SOFT"}


def test_invalid_context_errors_are_sanitized_and_stable() -> None:
    context = replace(
        build_replan_application_fixture(ROOT).context,
        idempotency_key_reference="secret-token",
    )
    with pytest.raises(ReplanApplicationError) as captured:
        require_replan_application_authorization(context)
    assert captured.value.reason is ReplanApplicationFailure.INVALID_INPUT
    assert "secret-token" not in str(captured.value)
