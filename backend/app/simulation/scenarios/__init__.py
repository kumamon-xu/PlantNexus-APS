"""Versioned ScenarioSpec and ScenarioManifest contract types."""

from importlib import import_module
from typing import TYPE_CHECKING, Any

from app.simulation.scenarios.contracts import (
    ScenarioManifestDocument,
    ScenarioSpecDocument,
    SimulationContractCode,
    SimulationContractError,
    SimulationTarget,
    require_simulation_target,
    validate_scenario_manifest_contract,
    validate_scenario_spec_contract,
)

if TYPE_CHECKING:
    from app.simulation.scenarios.disruption_replay import (
        BASELINE_ADVANCE_MODE,
        ContinuousReplanPort,
        ContinuousReplayResult,
        ContinuousReplayStepRequest,
        DisruptionKind,
        DisruptionReplayError,
        DisruptionReplayFailure,
        DisruptionReplayOrchestrator,
        DisruptionScenarioLibrary,
        DisruptionStep,
        ReplayBaseline,
        build_execution_config,
        build_execution_schedule,
        load_disruption_scenario_library,
    )
    from app.simulation.scenarios.p2_correctness import (
        CONSTRAINT_IDS,
        SCENARIO_IDS,
        CorrectnessCase,
        CorrectnessReplay,
        assignment_projection,
        execute_correctness_case,
        load_correctness_cases,
        materialize_constraint_mutation,
        run_correctness_checks,
        validate_correctness_case,
        verify_correctness_replay,
    )

_P2_CORRECTNESS_EXPORTS = frozenset(
    {
        "CONSTRAINT_IDS",
        "SCENARIO_IDS",
        "CorrectnessCase",
        "CorrectnessReplay",
        "assignment_projection",
        "execute_correctness_case",
        "load_correctness_cases",
        "materialize_constraint_mutation",
        "run_correctness_checks",
        "validate_correctness_case",
        "verify_correctness_replay",
    }
)

_P4_DISRUPTION_EXPORTS = frozenset(
    {
        "BASELINE_ADVANCE_MODE",
        "ContinuousReplanPort",
        "ContinuousReplayResult",
        "ContinuousReplayStepRequest",
        "DisruptionKind",
        "DisruptionReplayError",
        "DisruptionReplayFailure",
        "DisruptionReplayOrchestrator",
        "DisruptionScenarioLibrary",
        "DisruptionStep",
        "ReplayBaseline",
        "build_execution_config",
        "build_execution_schedule",
        "load_disruption_scenario_library",
    }
)


def __getattr__(name: str) -> Any:
    """Load executable correctness helpers lazily so ``python -m`` stays clean."""

    if name in _P2_CORRECTNESS_EXPORTS:
        module = import_module("app.simulation.scenarios.p2_correctness")
        return getattr(module, name)
    if name in _P4_DISRUPTION_EXPORTS:
        module = import_module("app.simulation.scenarios.disruption_replay")
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "BASELINE_ADVANCE_MODE",
    "CONSTRAINT_IDS",
    "SCENARIO_IDS",
    "ContinuousReplanPort",
    "ContinuousReplayResult",
    "ContinuousReplayStepRequest",
    "CorrectnessCase",
    "CorrectnessReplay",
    "DisruptionKind",
    "DisruptionReplayError",
    "DisruptionReplayFailure",
    "DisruptionReplayOrchestrator",
    "DisruptionScenarioLibrary",
    "DisruptionStep",
    "ReplayBaseline",
    "ScenarioManifestDocument",
    "ScenarioSpecDocument",
    "SimulationContractCode",
    "SimulationContractError",
    "SimulationTarget",
    "assignment_projection",
    "build_execution_config",
    "build_execution_schedule",
    "execute_correctness_case",
    "load_correctness_cases",
    "load_disruption_scenario_library",
    "materialize_constraint_mutation",
    "require_simulation_target",
    "run_correctness_checks",
    "validate_correctness_case",
    "validate_scenario_manifest_contract",
    "validate_scenario_spec_contract",
    "verify_correctness_replay",
]
