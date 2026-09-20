"""Search hints must leave the hard domain intact and never become fallback."""

from copy import deepcopy
from datetime import timedelta

import pytest

from app.domain.types import format_utc_instant, parse_utc_instant
from app.planning.backends.cp_sat import dispatch_hints
from app.planning.backends.cp_sat.backend import CpSatBackend
from app.planning.backends.cp_sat.model import build_core_model
from app.planning.backends.cp_sat.objectives import add_delivery_objective
from app.planning.policy.delivery import simulation_delivery_policy
from backend.tests.unit.test_global_cp_sat_strategy import delivery_problem, _limits


def hinted(problem):
    core = build_core_model(problem)
    objective = add_delivery_objective(problem, core)
    before = str(core.model.proto)
    accepted = dispatch_hints.add_dispatch_hints(problem, core, objective)
    values = dict(
        zip(core.model.proto.solution_hint.vars, core.model.proto.solution_hint.values)
    )
    core.model.clear_hints()
    assert str(core.model.proto) == before
    schedule = (
        {
            op.operation_id: (
                values[op.start.index],
                values[op.end.index],
                next(o.resource_id for o in op.options if values[o.presence.index]),
            )
            for op in core.operations
        }
        if accepted
        else {}
    )
    return accepted, schedule


def test_hints_do_not_change_domain_and_are_permutation_deterministic():
    problem = delivery_problem([4, 2, 3], [5, 3, 8], [2, 3, 1])
    accepted, schedule = hinted(problem)
    assert accepted
    shuffled = deepcopy(problem)
    shuffled["operation_instances"].reverse()
    shuffled["delivery_demands"].reverse()
    assert hinted(shuffled) == (accepted, schedule)


def test_calendar_release_material_and_transport_are_respected():
    problem = delivery_problem([2, 2], [3, 4], [1, 1], horizon_ticks=20)
    origin = parse_utc_instant(problem["horizon_start_utc"])

    def instant(tick):
        return format_utc_instant(origin + timedelta(seconds=tick * 60))

    first, second = problem["operation_instances"]
    first["release_at_utc"] = instant(1)
    first["material_ready_at_utc"] = instant(3)
    resource = deepcopy(problem["resources"][0])
    resource["resource_id"] = "RESOURCE-002"
    resource["workshop_id"] = "WORKSHOP-002"
    problem["resources"].append(resource)
    second["resource_options"][0]["resource_id"] = resource["resource_id"]
    problem["resource_unavailable_intervals"] = [
        {
            "calendar_id": problem["resources"][0]["calendar_id"],
            "resource_id": first["resource_options"][0]["resource_id"],
            "start_utc": instant(4),
            "end_utc": instant(7),
        }
    ]
    problem["precedence_edges"] = [
        {
            "precedence_edge_id": "EDGE-HINT",
            "predecessor_operation_id": first["operation_id"],
            "successor_operation_id": second["operation_id"],
            "min_lag_seconds": 61,
            "transport_lag_seconds": 181,
        }
    ]
    accepted, schedule = hinted(problem)
    assert accepted
    assert schedule[first["operation_id"]][:2] == (7, 9)
    assert schedule[second["operation_id"]][:2] == (13, 15)


@pytest.mark.parametrize(
    "reason", ["running", "locks", "anchors", "max_lag", "size", "work"]
)
def test_ineligible_or_exhausted_input_gets_no_hint(reason, monkeypatch):
    problem = delivery_problem([2, 2], [3, 4], [1, 1])
    core = build_core_model(problem)
    objective = add_delivery_objective(problem, core)
    if reason == "running":
        problem["operation_instances"][0]["status"] = "RUNNING"
    elif reason == "locks":
        problem["operation_locks"] = [{}]
    elif reason == "anchors":
        problem["historical_completion_anchors"] = [{}]
    elif reason == "max_lag":
        problem["precedence_edges"] = [{"max_lag_seconds": 10}]
    elif reason == "size":
        problem["operation_instances"] *= 65
    else:
        monkeypatch.setattr(dispatch_hints, "MAX_WORK_STEPS", 0)
    before = str(core.model.proto)
    assert not dispatch_hints.add_dispatch_hints(problem, core, objective)
    assert str(core.model.proto) == before


def test_unknown_does_not_return_hint_as_candidate():
    problem = delivery_problem([4, 2, 3], [5, 3, 8], [2, 3, 1])
    assert hinted(problem)[0]
    result = CpSatBackend().solve_delivery_with_evidence(
        problem, simulation_delivery_policy(), _limits(wall_time=1e-9)
    )
    assert result.solution["solver_status"] == "UNKNOWN"
    assert result.solution["assignments"] == []
    assert result.validation_report is None
