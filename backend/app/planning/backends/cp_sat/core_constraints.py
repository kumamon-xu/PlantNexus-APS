"""Fail-closed input boundary for the TASK-P2-05 core constraint slice."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import NoReturn, TypedDict, cast

from app.domain.types import duration_to_ticks, parse_utc_instant
from app.planning.contracts import DiagnosticDocument, SolverStatus
from app.planning.problem.contracts import PlanningProblemDocumentV2
from app.planning.problem.hashing import validate_built_problem_v2


CORE_CONSTRAINT_IDS = ("C-001", "C-003", "C-004", "C-010", "C-011")


class CoreModelReason(StrEnum):
    """Stable reasons for rejecting facts outside the bounded core model."""

    ZERO_RESOURCE_OPTIONS = "ZERO_RESOURCE_OPTIONS"
    DURATION_EXCEEDS_HORIZON = "DURATION_EXCEEDS_HORIZON"
    INVALID_HORIZON_TICKS = "INVALID_HORIZON_TICKS"
    UNSUPPORTED_PRECEDENCE_FACT = "UNSUPPORTED_PRECEDENCE_FACT"
    UNSUPPORTED_CALENDAR_FACT = "UNSUPPORTED_CALENDAR_FACT"
    UNSUPPORTED_RELEASE_MATERIAL_FACT = "UNSUPPORTED_RELEASE_MATERIAL_FACT"
    UNSUPPORTED_RUNNING_FACT = "UNSUPPORTED_RUNNING_FACT"
    UNSUPPORTED_LOCK_FACT = "UNSUPPORTED_LOCK_FACT"


class CoreModelInputError(ValueError):
    """Sanitized MODEL_INVALID rejection before a CP-SAT model is created."""

    code = "CP_SAT_CORE_MODEL_INPUT_ERROR"
    solver_status = SolverStatus.MODEL_INVALID

    def __init__(
        self,
        reason: CoreModelReason,
        *,
        field: str,
        entity_id: str,
        message: str,
    ) -> None:
        self.reason = reason
        self.field = field
        self.entity_id = entity_id
        self.message = message
        super().__init__(f"{self.code}/{reason.value} at {field} ({entity_id}): {message}")

    def diagnostic(self) -> DiagnosticDocument:
        """Return a stable JSON-compatible diagnostic."""

        return {
            "code": f"{self.code}_{self.reason.value}",
            "message": self.message,
        }


class CorePrecheckDocument(TypedDict):
    horizon_ticks: int
    operation_count: int
    option_count: int
    resource_count: int


def _reject(
    reason: CoreModelReason,
    *,
    field: str,
    entity_id: str,
    message: str,
) -> NoReturn:
    raise CoreModelInputError(
        reason,
        field=field,
        entity_id=entity_id,
        message=message,
    )


def _reject_zero_options_before_contract(problem: Mapping[str, object]) -> None:
    """Keep the requested zero-candidate reason stable before general validation."""

    operations = problem.get("operation_instances")
    if not isinstance(operations, list):
        return
    for index, operation_value in enumerate(operations):
        if not isinstance(operation_value, Mapping):
            continue
        operation = cast(Mapping[str, object], operation_value)
        options = operation.get("resource_options")
        if isinstance(options, list) and not options:
            operation_id = str(operation.get("operation_id", f"index:{index}"))
            _reject(
                CoreModelReason.ZERO_RESOURCE_OPTIONS,
                field=f"operation_instances[{index}].resource_options",
                entity_id=operation_id,
                message="Core assignment requires at least one explicit resource option",
            )


def precheck_core_problem(
    problem: Mapping[str, object],
) -> CorePrecheckDocument:
    """Validate the Problem and reject every non-vacuous P2-06/P2-07 fact."""

    _reject_zero_options_before_contract(problem)
    validate_built_problem_v2(problem)
    typed_problem = cast(PlanningProblemDocumentV2, problem)
    snapshot_id = typed_problem["snapshot_id"]
    horizon_start = parse_utc_instant(typed_problem["horizon_start_utc"])
    horizon_end = parse_utc_instant(typed_problem["horizon_end_utc"])
    tick_seconds = typed_problem["tick_seconds"]
    horizon_seconds = int((horizon_end - horizon_start).total_seconds())
    horizon_ticks = horizon_seconds // tick_seconds
    if horizon_ticks < 1:
        _reject(
            CoreModelReason.INVALID_HORIZON_TICKS,
            field="horizon_end_utc",
            entity_id=snapshot_id,
            message="Planning horizon contains no complete positive solver tick",
        )

    if typed_problem["precedence_edges"]:
        _reject(
            CoreModelReason.UNSUPPORTED_PRECEDENCE_FACT,
            field="precedence_edges",
            entity_id=snapshot_id,
            message="Precedence and transport facts are reserved for TASK-P2-06",
        )
    if typed_problem["resource_unavailable_intervals"]:
        _reject(
            CoreModelReason.UNSUPPORTED_CALENDAR_FACT,
            field="resource_unavailable_intervals",
            entity_id=snapshot_id,
            message="Resource calendar constraints are reserved for TASK-P2-06",
        )
    if typed_problem["operation_locks"]:
        _reject(
            CoreModelReason.UNSUPPORTED_LOCK_FACT,
            field="operation_locks",
            entity_id=snapshot_id,
            message="HARD and SOFT lock constraints are reserved for TASK-P2-07",
        )

    option_count = 0
    for operation_index, operation in enumerate(typed_problem["operation_instances"]):
        operation_id = operation["operation_id"]
        if operation["status"] == "RUNNING":
            _reject(
                CoreModelReason.UNSUPPORTED_RUNNING_FACT,
                field=f"operation_instances[{operation_index}].status",
                entity_id=operation_id,
                message="RUNNING execution facts are reserved for TASK-P2-07",
            )
        release_at = parse_utc_instant(operation["release_at_utc"])
        material_at = parse_utc_instant(operation["material_ready_at_utc"])
        if release_at > horizon_start or material_at > horizon_start:
            _reject(
                CoreModelReason.UNSUPPORTED_RELEASE_MATERIAL_FACT,
                field=f"operation_instances[{operation_index}]",
                entity_id=operation_id,
                message=(
                    "Non-vacuous release or material gates are reserved for "
                    "TASK-P2-06"
                ),
            )
        options = operation["resource_options"]
        option_count += len(options)
        for option_index, option in enumerate(options):
            duration_ticks = duration_to_ticks(
                option["final_duration_seconds"], tick_seconds
            )
            if duration_ticks > horizon_ticks:
                _reject(
                    CoreModelReason.DURATION_EXCEEDS_HORIZON,
                    field=(
                        f"operation_instances[{operation_index}]."
                        f"resource_options[{option_index}].final_duration_seconds"
                    ),
                    entity_id=operation_id,
                    message=(
                        "A resource option cannot fit wholly inside the planning "
                        "horizon; silent truncation or option removal is forbidden"
                    ),
                )

    return {
        "horizon_ticks": horizon_ticks,
        "operation_count": len(typed_problem["operation_instances"]),
        "option_count": option_count,
        "resource_count": len(typed_problem["resources"]),
    }


__all__ = [
    "CORE_CONSTRAINT_IDS",
    "CoreModelInputError",
    "CoreModelReason",
    "CorePrecheckDocument",
    "precheck_core_problem",
]
