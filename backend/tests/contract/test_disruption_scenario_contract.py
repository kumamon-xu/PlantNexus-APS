"""TEST-DISRUPTION-REPLAY-001 frozen contract and boundary tests."""

from __future__ import annotations

import ast
from collections.abc import Mapping
from copy import deepcopy
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
import pytest

from app.simulation.execution import ExecutionSimulator
from app.simulation.scenarios.disruption_replay import (
    ContinuousReplayStepRequest,
    DisruptionReplayError,
    DisruptionReplayFailure,
    build_execution_config,
    build_execution_schedule,
    load_disruption_scenario_library,
)
from app.simulation.scenarios.disruption_replay_check import (
    _ContractEvidencePort,
    _EvidenceIngress,
    _TamperedEvidencePort,
)
from app.simulation.scenarios.disruption_replay import DisruptionReplayOrchestrator


ROOT = Path(__file__).resolve().parents[3]
ASSET = ROOT / "fixtures/synthetic/P4-DISRUPTION-REPLAY/scenario-library.v1.json"


def test_all_eight_compiled_events_validate_against_frozen_p4_schema() -> None:
    schema = json.loads(
        (ROOT / "schemas/json/execution-event.schema.json").read_text(encoding="utf-8")
    )
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    library = load_disruption_scenario_library(ASSET)
    compiled = ExecutionSimulator().compile(
        build_execution_config(library), build_execution_schedule(library)
    )

    for event in compiled.events:
        validator.validate(event)


def test_scenario_orchestrator_has_no_repository_solver_api_or_wall_clock_shortcut() -> (
    None
):
    path = ROOT / "backend/app/simulation/scenarios/disruption_replay.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }

    assert not any(value.startswith("app.infrastructure") for value in imported)
    assert not any(value.startswith("app.api") for value in imported)
    assert "ortools" not in source
    assert "sqlalchemy" not in source
    assert "datetime.now" not in source
    assert "random." not in source


def test_incomplete_validator_or_fact_lock_evidence_fails_the_chain() -> None:
    library = load_disruption_scenario_library(ASSET)
    orchestrator = DisruptionReplayOrchestrator()

    with pytest.raises(DisruptionReplayError) as captured:
        orchestrator.run(library, _EvidenceIngress(), _TamperedEvidencePort())
    assert captured.value.reason is DisruptionReplayFailure.CHAIN_MISMATCH


def test_downstream_evidence_unknown_field_is_rejected() -> None:
    library = load_disruption_scenario_library(ASSET)

    class ExtraFieldPort(_ContractEvidencePort):
        def replay_step(
            self, request: ContinuousReplayStepRequest
        ) -> Mapping[str, object]:
            document = deepcopy(dict(super().replay_step(request)))
            document["unexpected"] = True
            return document

    with pytest.raises(DisruptionReplayError) as captured:
        DisruptionReplayOrchestrator().run(
            library,
            _EvidenceIngress(),
            ExtraFieldPort(),
        )
    assert captured.value.reason is DisruptionReplayFailure.INVALID_ASSET
