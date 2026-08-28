"""TEST-PROPERTY / TEST-SCENARIO-REPLAY P4-09 property evidence."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace

from hypothesis import given, settings, strategies as st

from app.simulation.execution import ExecutionSimulator
from app.simulation.execution.simulator_check import build_execution_simulator_fixture


class _Ingress:
    def __init__(self) -> None:
        self.ids: list[str] = []

    def ingest_event(self, document: Mapping[str, object]) -> object:
        self.ids.append(str(document["event_id"]))
        return object()


@settings(max_examples=12, deadline=None)
@given(order=st.permutations((0, 1, 2)))
def test_every_declaration_permutation_compiles_to_identical_bytes(
    order: list[int],
) -> None:
    fixture = build_execution_simulator_fixture()
    permuted = replace(
        fixture.schedule,
        events=tuple(fixture.schedule.events[index] for index in order),
    )
    simulator = ExecutionSimulator()
    expected = simulator.compile(fixture.config, fixture.schedule)
    observed = simulator.compile(fixture.config, permuted)

    assert observed.run_fingerprint == expected.run_fingerprint
    assert observed.event_keys == expected.event_keys
    assert observed.event_bytes == expected.event_bytes


@settings(max_examples=10, deadline=None)
@given(first_batch_size=st.integers(min_value=1, max_value=3))
def test_every_checkpoint_partition_reconstructs_the_full_prefix(
    first_batch_size: int,
) -> None:
    fixture = build_execution_simulator_fixture()
    simulator = ExecutionSimulator()
    ingress = _Ingress()
    first = simulator.run(
        fixture.config,
        fixture.schedule,
        ingress,
        max_events=first_batch_size,
    )
    resumed = simulator.run(
        fixture.config,
        fixture.schedule,
        ingress,
        checkpoint=first.checkpoint,
    )
    complete = simulator.run(fixture.config, fixture.schedule, _Ingress())

    assert resumed.event_bytes == complete.event_bytes
    assert resumed.stream_fingerprint == complete.stream_fingerprint
    assert ingress.ids == list(complete.event_ids)


@settings(max_examples=12, deadline=None)
@given(seed=st.integers(min_value=0, max_value=2**31 - 1))
def test_seed_is_replayable_and_part_of_stream_identity(seed: int) -> None:
    fixture = build_execution_simulator_fixture()
    config = replace(fixture.config, seed=seed)
    simulator = ExecutionSimulator()
    first = simulator.compile(config, fixture.schedule)
    second = simulator.compile(config, fixture.schedule)

    assert first.event_bytes == second.event_bytes
    assert first.run_fingerprint == second.run_fingerprint
    if seed != fixture.config.seed:
        baseline = simulator.compile(fixture.config, fixture.schedule)
        assert first.run_fingerprint != baseline.run_fingerprint
        assert first.event_bytes != baseline.event_bytes
