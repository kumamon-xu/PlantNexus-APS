"""TASK-P2-09 correctness matrix through formal P1/P2 boundaries."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pytest

from app.simulation.scenarios.p2_correctness import (
    CorrectnessCase,
    CorrectnessReplay,
    assignment_projection,
    execute_correctness_case,
    load_correctness_cases,
    verify_correctness_replay,
)

ROOT = Path(__file__).resolve().parents[3]
MATRIX_CAPABILITIES = {
    "P2-CROSS-WORKSHOP": {"SINGLE_FACTORY_MULTI_WORKSHOP", "DAG_ROUTING"},
    "P2-CALENDAR": {"MACHINE_CALENDAR"},
    "P2-MATERIAL-DELAY": {"RELEASE_AND_MATERIAL_GATE"},
    "P2-RUNNING": {"DAG_ROUTING", "ALTERNATIVE_RESOURCE", "RUNNING_OPERATION"},
    "P2-HARD-LOCK": {"ALTERNATIVE_RESOURCE", "HARD_SOFT_LOCK"},
}


@lru_cache(maxsize=1)
def _cases() -> dict[str, CorrectnessCase]:
    return {case.scenario_id: case for case in load_correctness_cases(ROOT)}


@lru_cache(maxsize=5)
def _replay(scenario_id: str) -> CorrectnessReplay:
    replay = execute_correctness_case(_cases()[scenario_id], root=ROOT)
    verify_correctness_replay(replay)
    return replay


def test_matrix_is_exactly_the_five_declared_versioned_scenarios() -> None:
    matrix_cases = {
        scenario_id: _cases()[scenario_id] for scenario_id in MATRIX_CAPABILITIES
    }

    assert set(matrix_cases) == set(MATRIX_CAPABILITIES)
    assert all(case.scenario["scenario_version"] == "1.0.0" for case in matrix_cases.values())
    assert all(case.profile["profile_id"] == "PROFILE-P2-CORRECTNESS-MATRIX" for case in matrix_cases.values())
    for scenario_id, case in matrix_cases.items():
        assert set(case.scenario["required_capabilities"]) == MATRIX_CAPABILITIES[
            scenario_id
        ]
        assert case.manifest["policy"]["policy_id"] == (
            "POLICY-P2-SIM-DELIVERY-OBJ001-001"
        )


@pytest.mark.parametrize("scenario_id", tuple(MATRIX_CAPABILITIES))
def test_matrix_case_uses_formal_chain_and_matches_fixed_outcome(
    scenario_id: str,
) -> None:
    replay = _replay(scenario_id)

    assert replay.import_document["import_package_version"] == "import-package.v2"
    assert replay.quality_report["status"] == "PASS"
    assert replay.expansion_document["expansion_version"] == "order-expansion.v1"
    assert replay.snapshot_document["snapshot_version"] == "planning-snapshot.v2"
    assert replay.problem["problem_version"] == "planning-problem.v2"
    solver = replay.solver_report["solver"]
    assert solver["backend_id"] == "cp-sat"
    assert solver["backend_version"] == "cp-sat-backend.v1"
    assert solver["solver_name"] == "Google-OR-Tools-CP-SAT"
    assert solver["solver_version"] == "9.15.6755"
    assert replay.validation_report["status"] == "PASS"
    assert assignment_projection(replay) == replay.case.expected["assignments"]


def test_matrix_positive_vectors_join_goldens_to_cover_all_constraints() -> None:
    covered = {
        constraint_id
        for case in _cases().values()
        for constraint_id in case.expected["positive_constraint_ids"]
    }

    assert covered == {f"C-{index:03d}" for index in range(1, 12)}
