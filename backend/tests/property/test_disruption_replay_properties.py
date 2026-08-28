"""TEST-SCENARIO-REPLAY fixed-seed replay and partition properties."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from app.simulation.execution import ExecutionSimulator
from app.simulation.scenarios.disruption_replay import (
    build_execution_config,
    build_execution_schedule,
    load_disruption_scenario_library,
)
from app.simulation.scenarios.disruption_replay_check import (
    _ContractEvidencePort,
    _EvidenceIngress,
)
from app.simulation.scenarios.disruption_replay import DisruptionReplayOrchestrator


ROOT = Path(__file__).resolve().parents[3]
ASSET = ROOT / "fixtures/synthetic/P4-DISRUPTION-REPLAY/scenario-library.v1.json"


def test_same_seed_replay_is_byte_exact_across_fresh_ports() -> None:
    library = load_disruption_scenario_library(ASSET)
    orchestrator = DisruptionReplayOrchestrator()

    first = orchestrator.run(library, _EvidenceIngress(), _ContractEvidencePort())
    second = orchestrator.run(library, _EvidenceIngress(), _ContractEvidencePort())

    assert first.canonical_bytes == second.canonical_bytes
    assert first.event_ids == second.event_ids
    assert first.event_stream_fingerprint == second.event_stream_fingerprint


def test_event_declaration_permutation_keeps_compiled_stream_bytes() -> None:
    library = load_disruption_scenario_library(ASSET)
    config = build_execution_config(library)
    schedule = build_execution_schedule(library)
    simulator = ExecutionSimulator()

    ordered = simulator.compile(config, schedule)
    permuted = simulator.compile(
        config, replace(schedule, events=tuple(reversed(schedule.events)))
    )

    assert ordered.event_bytes == permuted.event_bytes
    assert ordered.event_ids == permuted.event_ids
    assert ordered.stream_fingerprint == permuted.stream_fingerprint


def test_checkpoint_batch_partitions_equal_the_full_standard_prefix() -> None:
    library = load_disruption_scenario_library(ASSET)
    config = build_execution_config(library)
    schedule = build_execution_schedule(library)
    simulator = ExecutionSimulator()
    ingress = _EvidenceIngress()

    checkpoint = None
    for count in (1, 2, 2, 2, 1):
        result = simulator.run(
            config,
            schedule,
            ingress,
            checkpoint=checkpoint,
            max_events=count,
        )
        checkpoint = result.checkpoint
    full = simulator.run(config, schedule, _EvidenceIngress())

    assert checkpoint is not None
    assert checkpoint.last_emitted_position == 8
    assert checkpoint.prefix_fingerprint == full.stream_fingerprint
