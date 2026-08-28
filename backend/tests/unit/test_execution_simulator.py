"""TEST-EXECUTION-SIMULATOR-001 deterministic core unit evidence."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace

import pytest

from app.simulation.execution import (
    ExecutionSimulator,
    ExecutionSimulatorCheckpoint,
    ExecutionSimulatorError,
    ExecutionSimulatorFailure,
    ScheduledExecutionEvent,
    VersionedExecutionSchedule,
)
from app.simulation.execution.simulator_check import build_execution_simulator_fixture


class _RecordingIngress:
    def __init__(self) -> None:
        self.documents: list[dict[str, object]] = []

    def ingest_event(self, document: Mapping[str, object]) -> object:
        self.documents.append(dict(document))
        return object()


def test_virtual_clock_queue_and_standard_events_are_exact() -> None:
    fixture = build_execution_simulator_fixture()
    simulator = ExecutionSimulator()
    compiled = simulator.compile(fixture.config, fixture.schedule)
    ingress = _RecordingIngress()

    result = simulator.run(fixture.config, fixture.schedule, ingress)

    assert compiled.event_keys == (
        "material-ready-core-001",
        "duration-observed-core-001",
        "operation-started-core-001",
    )
    assert [event["source_position"] for event in result.events] == [1, 2, 3]
    assert [event["occurred_at_utc"] for event in result.events] == [
        "2026-08-28T08:00:10Z",
        "2026-08-28T08:00:10Z",
        "2026-08-28T08:00:20Z",
    ]
    assert tuple(ingress.documents) == result.events
    assert result.checkpoint.last_emitted_position == 3


def test_same_input_and_declaration_permutation_are_byte_exact() -> None:
    fixture = build_execution_simulator_fixture()
    simulator = ExecutionSimulator()
    first = simulator.run(fixture.config, fixture.schedule, _RecordingIngress())
    second = simulator.run(fixture.config, fixture.schedule, _RecordingIngress())
    permuted = replace(
        fixture.schedule, events=tuple(reversed(fixture.schedule.events))
    )
    third = simulator.run(fixture.config, permuted, _RecordingIngress())

    assert first.event_bytes == second.event_bytes == third.event_bytes
    assert first.stream_fingerprint == second.stream_fingerprint
    assert first.compiled.run_fingerprint == third.compiled.run_fingerprint
    assert fixture.schedule.fingerprint == permuted.fingerprint


def test_checkpoint_restart_emits_only_the_unapplied_suffix() -> None:
    fixture = build_execution_simulator_fixture()
    simulator = ExecutionSimulator()
    ingress = _RecordingIngress()

    first = simulator.run(
        fixture.config, fixture.schedule, ingress, max_events=1
    )
    resumed = simulator.run(
        fixture.config,
        fixture.schedule,
        ingress,
        checkpoint=first.checkpoint,
    )

    assert first.emitted_positions == (1,)
    assert resumed.emitted_positions == (2, 3)
    assert len(ingress.documents) == 3
    assert tuple(ingress.documents) == resumed.events


def test_invalid_checkpoint_stale_source_and_production_fail_before_ingress() -> None:
    fixture = build_execution_simulator_fixture()
    simulator = ExecutionSimulator()
    ingress = _RecordingIngress()
    compiled = simulator.compile(fixture.config, fixture.schedule)
    checkpoint = ExecutionSimulatorCheckpoint(
        checkpoint_version="execution-simulator-checkpoint.v1",
        run_fingerprint=compiled.run_fingerprint,
        last_emitted_position=1,
        prefix_fingerprint=f"sha256:{'0' * 64}",
    )

    with pytest.raises(ExecutionSimulatorError) as checkpoint_error:
        simulator.run(
            fixture.config,
            fixture.schedule,
            ingress,
            checkpoint=checkpoint,
        )
    assert checkpoint_error.value.reason is ExecutionSimulatorFailure.CHECKPOINT_MISMATCH

    stale = replace(
        fixture.schedule, scenario_fingerprint=f"sha256:{'b' * 64}"
    )
    with pytest.raises(ExecutionSimulatorError) as stale_error:
        simulator.run(fixture.config, stale, ingress)
    assert stale_error.value.reason is ExecutionSimulatorFailure.SOURCE_MISMATCH

    with pytest.raises(ExecutionSimulatorError) as production_error:
        replace(fixture.config, environment="PRODUCTION")
    assert production_error.value.reason is ExecutionSimulatorFailure.PRODUCTION_FORBIDDEN
    assert ingress.documents == []


def test_schedule_rejects_duplicates_unknown_types_and_unaligned_offsets() -> None:
    fixture = build_execution_simulator_fixture()
    duplicate = fixture.schedule.events[0]
    with pytest.raises(ExecutionSimulatorError) as duplicate_error:
        replace(fixture.schedule, events=(duplicate, duplicate))
    assert duplicate_error.value.reason is ExecutionSimulatorFailure.ORDERING_VIOLATION

    with pytest.raises(ExecutionSimulatorError) as type_error:
        ScheduledExecutionEvent.create(
            event_key="unknown-event",
            offset_seconds=1,
            event_type="P5_REALITY_CALIBRATED",
            payload={"kind": "P5_REALITY_CALIBRATED"},
        )
    assert type_error.value.reason is ExecutionSimulatorFailure.VERSION_MISMATCH

    unaligned_clock = replace(
        fixture.config,
        virtual_clock=replace(
            fixture.config.virtual_clock, resolution_seconds=5
        ),
    )
    unaligned_event = ScheduledExecutionEvent.create(
        event_key="unaligned-duration",
        offset_seconds=11,
        event_type="PROCESSING_DURATION_CHANGED",
        payload={
            "kind": "PROCESSING_DURATION_CHANGED",
            "operation_id": "operation-unaligned",
            "final_duration_seconds": 1,
            "duration_source": "unit-test",
            "source_version": "1.0.0",
        },
    )
    schedule = VersionedExecutionSchedule(
        schedule_version="execution-event-schedule.v1",
        config_id="unaligned-config",
        config_version="1.0.0",
        base_schedule_content_fingerprint=(
            fixture.config.base_schedule_version.content_fingerprint
        ),
        scenario_fingerprint=fixture.config.scenario.fingerprint,
        factory_profile_fingerprint=fixture.config.factory_profile.fingerprint,
        generator_fingerprint=fixture.config.generator.fingerprint,
        events=(unaligned_event,),
    )
    with pytest.raises(ExecutionSimulatorError) as alignment_error:
        ExecutionSimulator().compile(unaligned_clock, schedule)
    assert alignment_error.value.reason is ExecutionSimulatorFailure.ORDERING_VIOLATION
