"""TASK-P4-08 authority and data-plane isolation regression tests."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest

from app.application.replan_application import ReplanApplicationService
from app.application.replan_application_check import (
    build_replan_application_fixture,
)
from app.domain.replan_application import (
    ReplanApplicationError,
    ReplanApplicationFailure,
)


ROOT = Path(__file__).resolve().parents[3]


class NeverCalledBoundary:
    """Records any lookup/transaction attempted past an authorization gate."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def __call__(self) -> Any:
        self.calls.append("transaction")
        raise AssertionError("persistence must not be reached")

    def __getattr__(self, name: str) -> Any:
        def called(*_args: object, **_kwargs: object) -> Any:
            self.calls.append(name)
            raise AssertionError("repository must not be reached")

        return called


def _service(boundary: NeverCalledBoundary) -> ReplanApplicationService:
    adapter = cast(Any, boundary)
    return ReplanApplicationService(
        transaction_factory=adapter,
        schedule_repository=adapter,
        publication_repository=adapter,
        snapshot_repository=adapter,
        request_repository=adapter,
        lineage_repository=adapter,
        audit_repository=adapter,
        strategy=adapter,
    )


@pytest.mark.parametrize(
    "context_changes",
    [
        {"data_plane": "PRODUCTION"},
        {"environment": "PRODUCTION"},
        {"production_binding": True},
    ],
)
def test_production_is_denied_before_idempotency_or_result_lookup(
    context_changes: dict[str, object],
) -> None:
    fixture = build_replan_application_fixture(ROOT)
    boundary = NeverCalledBoundary()
    with pytest.raises(ReplanApplicationError) as captured:
        _service(boundary).execute(
            fixture.input,
            replace(fixture.context, **context_changes),
        )
    assert captured.value.reason is ReplanApplicationFailure.AUTHORIZATION_DENIED
    assert boundary.calls == []


def test_context_lineage_mismatch_is_denied_before_any_repository_access() -> None:
    fixture = build_replan_application_fixture(ROOT)
    boundary = NeverCalledBoundary()
    with pytest.raises(ReplanApplicationError) as captured:
        _service(boundary).execute(
            fixture.input,
            replace(fixture.context, correlation_id="cross-scope-correlation"),
        )
    assert captured.value.reason is ReplanApplicationFailure.LINEAGE_MISMATCH
    assert boundary.calls == []
