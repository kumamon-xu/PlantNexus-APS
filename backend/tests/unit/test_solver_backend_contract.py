"""TASK-P2-03 exact-version and CP-SAT backend foundation evidence."""

from __future__ import annotations

import ast
import copy
import inspect
import json
from pathlib import Path
from typing import Any, cast

import pytest

from app.planning.backends import SolverBackend as ExportedSolverBackend
from app.planning.backends.contracts import (
    BackendFailureReason,
    SolverBackendError,
)
from app.planning.backends.cp_sat import (
    ORTOOLS_VERSION,
    CpSatBackend,
    backend_identity,
    native_status_contract,
    parameters_for_limits,
    probe_empty_model,
    probe_model_invalid,
    solver_status_from_cp_sat,
)
from app.planning.backends.cp_sat import backend as backend_module
from app.planning.contracts import (
    SolverBackend as CanonicalSolverBackend,
    SolverStatus,
)
from app.planning.policy.contracts import (
    PlanningPolicyDocument,
    SolveLimitsDocument,
)
from app.planning.problem.contracts import PlanningProblemDocumentV2


ROOT = Path(__file__).resolve().parents[3]


def _load_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _samples() -> tuple[
    PlanningProblemDocumentV2,
    PlanningPolicyDocument,
    SolveLimitsDocument,
]:
    sample_root = ROOT / "schemas" / "samples"
    return (
        cast(
            PlanningProblemDocumentV2,
            _load_json(sample_root / "planning-problem.v2.synthetic.json"),
        ),
        cast(
            PlanningPolicyDocument,
            _load_json(sample_root / "planning-policy.v1.synthetic.json"),
        ),
        cast(
            SolveLimitsDocument,
            _load_json(sample_root / "solve-limits.v1.synthetic.json"),
        ),
    )


def test_public_backend_surface_reuses_the_solver_neutral_protocol() -> None:
    assert ExportedSolverBackend is CanonicalSolverBackend
    source = (ROOT / "backend/app/planning/backends/contracts.py").read_text(
        encoding="utf-8"
    )
    assert "ortools" not in source.lower()


def test_backend_identity_is_exact_and_version_drift_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identity = backend_identity()
    assert identity == {
        "backend_id": "cp-sat",
        "backend_version": "cp-sat-backend.v1",
        "solver_name": "Google OR-Tools CP-SAT",
        "solver_version": "9.15.6755",
    }
    assert ORTOOLS_VERSION == "9.15.6755"

    monkeypatch.setattr(backend_module.ortools, "__version__", "9.15.drift")
    with pytest.raises(SolverBackendError) as captured:
        backend_identity()
    assert captured.value.reason is BackendFailureReason.VERSION_MISMATCH
    assert captured.value.solver_status is SolverStatus.FAILED
    assert "9.15.drift" not in str(captured.value)


def test_native_status_mapping_is_total_and_unknown_codes_fail_closed() -> None:
    mapping = native_status_contract()
    assert tuple(row["native_name"] for row in mapping) == (
        "UNKNOWN",
        "MODEL_INVALID",
        "FEASIBLE",
        "INFEASIBLE",
        "OPTIMAL",
    )
    assert tuple(row["solver_status"] for row in mapping) == (
        "UNKNOWN",
        "MODEL_INVALID",
        "FEASIBLE",
        "INFEASIBLE",
        "OPTIMAL",
    )
    assert solver_status_from_cp_sat(0) is SolverStatus.UNKNOWN
    assert solver_status_from_cp_sat(0, cancelled=True) is SolverStatus.CANCELLED

    with pytest.raises(SolverBackendError) as captured:
        solver_status_from_cp_sat(999)
    assert captured.value.reason is BackendFailureReason.UNSUPPORTED_NATIVE_STATUS
    assert captured.value.solver_status is SolverStatus.FAILED


def test_solve_limits_map_to_canonical_explicit_parameters() -> None:
    _, _, limits = _samples()
    assert parameters_for_limits(limits) == [
        {
            "name": "log_search_progress",
            "value": False,
            "source": "BACKEND",
        },
        {
            "name": "max_time_in_seconds",
            "value": 30.0,
            "source": "SOLVE_LIMITS",
        },
        {
            "name": "num_search_workers",
            "value": 1,
            "source": "SOLVE_LIMITS",
        },
        {
            "name": "random_seed",
            "value": 20260820,
            "source": "SOLVE_LIMITS",
        },
    ]

    invalid = cast(SolveLimitsDocument, copy.deepcopy(limits))
    invalid["max_workers"] = cast(Any, True)
    with pytest.raises(ValueError, match="INVALID_METRIC"):
        parameters_for_limits(invalid)


def test_empty_and_model_invalid_smokes_are_json_only_and_not_feasibility() -> None:
    _, _, limits = _samples()
    empty = probe_empty_model(limits)
    invalid = probe_model_invalid(limits)

    assert empty["smoke_kind"] == "EMPTY_MODEL"
    assert empty["solver_status"] == "OPTIMAL"
    assert empty["model_metrics"] == {
        "variables": 0,
        "constraints": 0,
        "optional_intervals": 0,
    }
    assert invalid["smoke_kind"] == "MODEL_INVALID"
    assert invalid["solver_status"] == "MODEL_INVALID"
    assert invalid["model_metrics"] == {
        "variables": 1,
        "constraints": 0,
        "optional_intervals": 0,
    }
    for result in (empty, invalid):
        assert result["business_feasibility"] == "NOT_EVALUATED"
        assert result["candidate_produced"] is False
        assert result["wall_time_seconds"] >= 0
        payload = json.dumps(result, sort_keys=True)
        assert "CpModel" not in payload
        assert "CpSolver" not in payload


def test_foundation_protocol_remains_stable_after_core_model_activation() -> None:
    backend = CpSatBackend()
    assert backend.identity == backend_identity()
    assert tuple(inspect.signature(CpSatBackend.solve).parameters) == (
        "self",
        "problem",
        "policy",
        "limits",
    )


def test_ortools_imports_are_confined_to_cp_sat_backend_package() -> None:
    app_root = ROOT / "backend" / "app"
    allowed_prefix = "backend/app/planning/backends/cp_sat/"
    observed: list[str] = []
    for path in sorted(app_root.rglob("*.py")):
        relative = path.relative_to(ROOT).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            modules: list[str] = []
            if isinstance(node, ast.Import):
                modules.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.append(node.module)
            for module in modules:
                if module == "ortools" or module.startswith("ortools."):
                    observed.append(relative)
                    assert relative.startswith(allowed_prefix)
    assert set(observed) == {
        "backend/app/planning/backends/cp_sat/backend.py",
        "backend/app/planning/backends/cp_sat/fact_lock_constraints.py",
        "backend/app/planning/backends/cp_sat/model.py",
        "backend/app/planning/backends/cp_sat/objectives.py",
        "backend/app/planning/backends/cp_sat/replan_backend.py",
        "backend/app/planning/backends/cp_sat/replan_model.py",
        "backend/app/planning/backends/cp_sat/solution_mapper.py",
        "backend/app/planning/backends/cp_sat/status.py",
        "backend/app/planning/backends/cp_sat/temporal_constraints.py",
    }
