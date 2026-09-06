"""Focused facade and dispatch behavior for P8-06."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from celery import Celery
import pytest
from sqlalchemy import text

from app.application.runtime_facade import RuntimeDispatchWindow, RuntimeFacadeError
from app.data_validation.canonical_ingress import canonical_json_bytes
from app.runtime_composition import RuntimeProcess, compose_runtime
from backend.tests.p8_runtime_support import (
    FixedIdentityFactory,
    RecordingCelery,
    command_context,
    dispatch_window,
    ingress_context,
    runtime_settings,
)
from backend.tests.p8_solver_worker_support import migrated_engine, worker_request


def _settings(tmp_path: Path):
    database_path = tmp_path / "facade.db"
    engine, _ = migrated_engine(database_path)
    engine.dispose()
    return runtime_settings(
        tmp_path, database_url=f"sqlite:///{database_path.as_posix()}"
    )


def test_facade_exact_replay_reuses_run_without_duplicate_dispatch(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    publisher = RecordingCelery()
    composition = compose_runtime(
        settings,
        process=RuntimeProcess.API,
        dispatch_client=cast(Celery, publisher),
        identity_factory=FixedIdentityFactory("dispatch-one", "dispatch-two"),
    )
    try:
        assert composition.application is not None
        request = worker_request()
        context = ingress_context(request, composition.descriptor)
        first = composition.application.submit_canonical(
            canonical_json_bytes(request),
            context=context,
            dispatch_window=dispatch_window(),
        )
        replay = composition.application.submit_canonical(
            canonical_json_bytes(request),
            context=context,
            dispatch_window=dispatch_window(),
        )
        assert first.planning_run is not None
        assert replay.planning_run is not None
        assert first.planning_run.aggregate.canonical_bytes == (
            replay.planning_run.aggregate.canonical_bytes
        )
        assert replay.ingress is not None and replay.ingress.replayed is True
        assert len(publisher.messages) == 1
        assert first.dispatch is not None
        assert replay.dispatch is None
    finally:
        composition.close()


def test_dispatch_failure_is_sanitized_and_durably_marks_attempt(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    publisher = RecordingCelery(fail=True)
    composition = compose_runtime(
        settings,
        process=RuntimeProcess.API,
        dispatch_client=cast(Celery, publisher),
        identity_factory=FixedIdentityFactory("dispatch-failure"),
    )
    request = worker_request()
    try:
        assert composition.application is not None
        with pytest.raises(RuntimeFacadeError) as captured:
            composition.application.submit_canonical(
                canonical_json_bytes(request),
                context=ingress_context(request, composition.descriptor),
                dispatch_window=dispatch_window(),
            )
        assert captured.value.code == "QUEUE_FAILED"
        assert "do-not-leak" not in str(captured.value)
        with composition.database.engine.connect() as connection:
            planning_run_id = connection.scalar(
                text("SELECT planning_run_id FROM planning_runs")
            )
        assert isinstance(planning_run_id, str)
        model = composition.application.read_planning_run(
            planning_run_id,
            context=command_context(request),
        )
        assert model.attempts[-1].document["status"] == "DISPATCH_FAILED"
        assert model.attempts[-1].document["failure_code"] == (
            "BROKER_DISPATCH_FAILED"
        )
    finally:
        composition.close()


def test_dispatch_window_rejects_non_utc_or_reversed_values() -> None:
    with pytest.raises(ValueError):
        RuntimeDispatchWindow(
            available_at_utc="2026-09-05T00:00:00",
            timeout_at_utc="2026-09-05T01:00:00Z",
        )
    with pytest.raises(ValueError):
        RuntimeDispatchWindow(
            available_at_utc="2026-09-05T02:00:00Z",
            timeout_at_utc="2026-09-05T01:00:00Z",
        )
