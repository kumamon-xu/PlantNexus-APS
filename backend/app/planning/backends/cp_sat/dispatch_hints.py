"""Bounded deterministic initial values, never constraints or product candidates."""

from __future__ import annotations

from app.domain.types import parse_utc_instant
from app.planning.backends.cp_sat.model import CoreCpSatModel
from app.planning.backends.cp_sat.objectives import DeliveryObjectiveModel
from app.planning.backends.cp_sat.temporal_constraints import calendar_tick_blocks
from app.planning.problem.contracts import PlanningProblemDocumentV2

SEARCH_POLICY = "global-dispatch-hints.v1"
MAX_WORK_STEPS = 200_000


class _WorkLimit(Exception):
    pass


def add_dispatch_hints(
    problem: PlanningProblemDocumentV2,
    core: CoreCpSatModel,
    objective: DeliveryObjectiveModel,
) -> bool:
    """Offer the best complete dispatch; native search may ignore every value."""
    operations = problem["operation_instances"]
    edges = problem["precedence_edges"]
    if (
        not operations
        or len(operations) > 128
        or sum(len(op["resource_options"]) for op in operations) > 4096
        or len(edges) > 4096
        or len(problem["resource_unavailable_intervals"]) > 4096
        or problem["historical_completion_anchors"]
        or problem["operation_locks"]
        or any(op["status"] != "NOT_STARTED" for op in operations)
        or any(edge.get("max_lag_seconds") is not None for edge in edges)
    ):
        return False
    tick = problem["tick_seconds"]
    origin = parse_utc_instant(problem["horizon_start_utc"])

    def seconds(instant: str) -> int:
        return int((parse_utc_instant(instant) - origin).total_seconds())

    def ceil_ticks(value: int) -> int:
        return -(-value // tick)

    by_id = {op["operation_id"]: op for op in operations}
    variables = {op.operation_id: op for op in core.operations}
    demands = {d.demand_order_id: d for d in objective.demands}
    workshops = {r["resource_id"]: r["workshop_id"] for r in problem["resources"]}
    incoming = {op_id: [] for op_id in by_id}
    for edge in edges:
        incoming[edge["successor_operation_id"]].append(edge)
    gates = {
        op_id: max(
            0,
            ceil_ticks(seconds(op["release_at_utc"])),
            ceil_ticks(seconds(op["material_ready_at_utc"])),
        )
        for op_id, op in by_id.items()
    }
    blocks = calendar_tick_blocks(problem, horizon_ticks=core.horizon_ticks)
    work = 0

    def step() -> None:
        nonlocal work
        work += 1
        if work > MAX_WORK_STEPS:
            raise _WorkLimit

    def score(placed: dict[str, tuple[int, int, str]]) -> int:
        return sum(
            demand.priority_weight
            * max(
                0,
                max(
                    placed[op_id][1]
                    for op_id, op in by_id.items()
                    if op["demand_order_id"] == demand.demand_order_id
                )
                * tick
                - demand.due_offset_seconds,
            )
            for demand in objective.demands
        )

    best: dict[str, tuple[int, int, str]] | None = None
    best_score: int | None = None
    try:
        for rule in range(5):
            placed: dict[str, tuple[int, int, str]] = {}
            occupied = {resource: list(values) for resource, values in blocks.items()}
            while len(placed) < len(by_id):
                choices = []
                for op_id in sorted(by_id.keys() - placed.keys()):
                    step()
                    predecessors = incoming[op_id]
                    if any(
                        e["predecessor_operation_id"] not in placed
                        for e in predecessors
                    ):
                        continue
                    options = []
                    for option in variables[op_id].options:
                        step()
                        resource = option.resource_id
                        start = gates[op_id]
                        for edge in predecessors:
                            step()
                            _, end, previous = placed[edge["predecessor_operation_id"]]
                            lag = edge["min_lag_seconds"]
                            if workshops[previous] != workshops[resource]:
                                lag = max(lag, edge["transport_lag_seconds"])
                            start = max(start, end + ceil_ticks(lag))
                        for lower, upper in sorted(occupied[resource]):
                            step()
                            if start + option.duration_ticks <= lower:
                                break
                            if start < upper:
                                start = upper
                        end = start + option.duration_ticks
                        if end <= core.horizon_ticks:
                            options.append(
                                (end, start, option.duration_ticks, resource)
                            )
                    if not options:
                        continue
                    end, start, duration, resource = min(options)
                    op = by_id[op_id]
                    demand = demands[op["demand_order_id"]]
                    due = demand.due_offset_seconds
                    release = seconds(op["release_at_utc"])
                    keys = (
                        (end, start, duration, resource, op_id),
                        (due, release, op["demand_order_id"], op_id),
                        (
                            min(o.duration_ticks for o in variables[op_id].options),
                            due,
                            op_id,
                        ),
                        (
                            -demand.priority_weight,
                            due,
                            release,
                            op["demand_order_id"],
                            op_id,
                        ),
                        (release, op["demand_order_id"], op_id),
                    )
                    choices.append((keys[rule], op_id, start, end, resource))
                if not choices:
                    break
                _, op_id, start, end, resource = min(choices)
                placed[op_id] = (start, end, resource)
                occupied[resource].append((start, end))
            if len(placed) == len(by_id):
                value = score(placed)
                if best_score is None or value < best_score:
                    best, best_score = placed, value
    except _WorkLimit:
        return False
    if best is None:
        return False
    for op in core.operations:
        start, end, resource = best[op.operation_id]
        core.model.add_hint(op.start, start)
        core.model.add_hint(op.end, end)
        for option in op.options:
            core.model.add_hint(option.presence, int(option.resource_id == resource))
    for demand in objective.demands:
        completion = max(
            best[op_id][1]
            for op_id, op in by_id.items()
            if op["demand_order_id"] == demand.demand_order_id
        )
        core.model.add_hint(demand.completion_tick, completion)
        core.model.add_hint(
            demand.tardiness_seconds,
            max(0, completion * tick - demand.due_offset_seconds),
        )
    assert best_score is not None
    core.model.add_hint(objective.total_weighted_tardiness_seconds, best_score)
    return True
