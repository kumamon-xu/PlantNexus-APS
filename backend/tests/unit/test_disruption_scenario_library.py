"""TEST-DISRUPTION-REPLAY-001 versioned P4 scenario-library unit tests."""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import pytest

from app.simulation.execution import ExecutionSimulator
from app.simulation.scenarios.disruption_replay import (
    DisruptionReplayError,
    DisruptionReplayFailure,
    EXPECTED_STEP_EVENTS,
    build_execution_config,
    build_execution_schedule,
    load_disruption_scenario_library,
)


ROOT = Path(__file__).resolve().parents[3]
ASSET = ROOT / "fixtures/synthetic/P4-DISRUPTION-REPLAY/scenario-library.v1.json"


def test_versioned_library_has_exact_five_step_eight_event_coverage() -> None:
    library = load_disruption_scenario_library(ASSET)

    assert library.asset_id == "SIM-P4-DISRUPTION-REPLAY-001"
    assert library.asset_version == "1.0.0"
    assert library.seed == 20260828
    assert library.freeze_window_seconds == 900
    assert tuple(step.disruption_kind for step in library.steps) == tuple(
        expected[0] for expected in EXPECTED_STEP_EVENTS
    )
    assert tuple(
        event.event_type for step in library.steps for event in step.events
    ) == tuple(
        value for _, event_types in EXPECTED_STEP_EVENTS for value in event_types
    )
    assert sum(len(step.events) for step in library.steps) == 8


def test_library_builds_the_standard_simulator_contract_without_private_events() -> (
    None
):
    library = load_disruption_scenario_library(ASSET)
    config = build_execution_config(library)
    schedule = build_execution_schedule(library)
    compiled = ExecutionSimulator().compile(config, schedule)

    assert len(compiled.events) == 8
    assert compiled.event_keys == tuple(
        event.event_key for step in library.steps for event in step.events
    )
    assert {event["execution_event_version"] for event in compiled.events} == {
        "execution-event.v1"
    }
    assert {event["data_plane"] for event in compiled.events} == {"SIMULATION"}
    assert all(event["production_binding"] is False for event in compiled.events)


def test_seed_is_part_of_run_and_event_identity() -> None:
    library = load_disruption_scenario_library(ASSET)
    changed = replace(library, seed=library.seed + 1)
    simulator = ExecutionSimulator()

    first = simulator.compile(
        build_execution_config(library), build_execution_schedule(library)
    )
    second = simulator.compile(
        build_execution_config(changed), build_execution_schedule(changed)
    )

    assert first.run_fingerprint != second.run_fingerprint
    assert first.event_ids != second.event_ids


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        (
            "target_environment",
            "PRODUCTION",
            DisruptionReplayFailure.PRODUCTION_FORBIDDEN,
        ),
        ("production_binding", True, DisruptionReplayFailure.PRODUCTION_FORBIDDEN),
        (
            "library_version",
            "p4-disruption-scenario-library.v2",
            DisruptionReplayFailure.VERSION_MISMATCH,
        ),
    ],
)
def test_unknown_version_or_production_plane_fails_closed(
    tmp_path: Path,
    field: str,
    value: object,
    reason: DisruptionReplayFailure,
) -> None:
    document = json.loads(ASSET.read_text(encoding="utf-8"))
    document[field] = value
    path = tmp_path / "library.json"
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(DisruptionReplayError) as captured:
        load_disruption_scenario_library(path)
    assert captured.value.reason is reason
