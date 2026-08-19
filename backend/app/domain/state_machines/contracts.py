"""Enumerated states and explicit transition relations for the three P0 machines."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import Literal, TypedDict

from app.domain.errors import (
    ProductErrorCategory,
    ProductErrorCode,
    category_for_error_code,
)


class StateMachineName(StrEnum):
    PLANNING_RUN = "PLANNING_RUN"
    SCHEDULE_VERSION = "SCHEDULE_VERSION"
    EXPORT_JOB = "EXPORT_JOB"


class PlanningRunState(StrEnum):
    CREATED = "CREATED"
    INGESTING = "INGESTING"
    VALIDATING = "VALIDATING"
    SNAPSHOTTED = "SNAPSHOTTED"
    BUILDING = "BUILDING"
    SOLVING = "SOLVING"
    SOLVED = "SOLVED"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    DATA_REJECTED = "DATA_REJECTED"
    MODEL_INVALID = "MODEL_INVALID"
    INFEASIBLE = "INFEASIBLE"
    NO_SOLUTION_WITHIN_LIMIT = "NO_SOLUTION_WITHIN_LIMIT"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class ScheduleVersionState(StrEnum):
    DRAFT = "DRAFT"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    APPROVED = "APPROVED"
    PUBLISHED = "PUBLISHED"
    SUPERSEDED = "SUPERSEDED"
    REJECTED = "REJECTED"


class ExportJobState(StrEnum):
    CREATED = "CREATED"
    EXPORTING = "EXPORTING"
    EXPORTED = "EXPORTED"
    EXPORT_FAILED = "EXPORT_FAILED"
    CANCELLED = "CANCELLED"


class StateTransitionDocument(TypedDict):
    state_transition_version: Literal["state-transition.v1"]
    machine: Literal["PLANNING_RUN", "SCHEDULE_VERSION", "EXPORT_JOB"]
    from_state: str
    to_state: str


def _pairs(*values: tuple[StrEnum, StrEnum]) -> frozenset[tuple[str, str]]:
    return frozenset((source.value, target.value) for source, target in values)


_PLANNING_RUN_TRANSITIONS = _pairs(
    (PlanningRunState.CREATED, PlanningRunState.INGESTING),
    (PlanningRunState.CREATED, PlanningRunState.CANCELLED),
    (PlanningRunState.CREATED, PlanningRunState.FAILED),
    (PlanningRunState.INGESTING, PlanningRunState.VALIDATING),
    (PlanningRunState.INGESTING, PlanningRunState.DATA_REJECTED),
    (PlanningRunState.INGESTING, PlanningRunState.CANCELLED),
    (PlanningRunState.INGESTING, PlanningRunState.FAILED),
    (PlanningRunState.VALIDATING, PlanningRunState.SNAPSHOTTED),
    (PlanningRunState.VALIDATING, PlanningRunState.DATA_REJECTED),
    (PlanningRunState.VALIDATING, PlanningRunState.CANCELLED),
    (PlanningRunState.VALIDATING, PlanningRunState.FAILED),
    (PlanningRunState.SNAPSHOTTED, PlanningRunState.BUILDING),
    (PlanningRunState.SNAPSHOTTED, PlanningRunState.CANCELLED),
    (PlanningRunState.SNAPSHOTTED, PlanningRunState.FAILED),
    (PlanningRunState.BUILDING, PlanningRunState.SOLVING),
    (PlanningRunState.BUILDING, PlanningRunState.MODEL_INVALID),
    (PlanningRunState.BUILDING, PlanningRunState.CANCELLED),
    (PlanningRunState.BUILDING, PlanningRunState.FAILED),
    (PlanningRunState.SOLVING, PlanningRunState.SOLVED),
    (PlanningRunState.SOLVING, PlanningRunState.MODEL_INVALID),
    (PlanningRunState.SOLVING, PlanningRunState.INFEASIBLE),
    (PlanningRunState.SOLVING, PlanningRunState.NO_SOLUTION_WITHIN_LIMIT),
    (PlanningRunState.SOLVING, PlanningRunState.CANCELLED),
    (PlanningRunState.SOLVING, PlanningRunState.FAILED),
    (PlanningRunState.SOLVED, PlanningRunState.VERIFYING),
    (PlanningRunState.SOLVED, PlanningRunState.CANCELLED),
    (PlanningRunState.SOLVED, PlanningRunState.FAILED),
    (PlanningRunState.VERIFYING, PlanningRunState.COMPLETED),
    (PlanningRunState.VERIFYING, PlanningRunState.VALIDATION_FAILED),
    (PlanningRunState.VERIFYING, PlanningRunState.CANCELLED),
    (PlanningRunState.VERIFYING, PlanningRunState.FAILED),
)
_SCHEDULE_VERSION_TRANSITIONS = _pairs(
    (ScheduleVersionState.DRAFT, ScheduleVersionState.READY_FOR_REVIEW),
    (ScheduleVersionState.READY_FOR_REVIEW, ScheduleVersionState.APPROVED),
    (ScheduleVersionState.READY_FOR_REVIEW, ScheduleVersionState.REJECTED),
    (ScheduleVersionState.APPROVED, ScheduleVersionState.PUBLISHED),
    (ScheduleVersionState.PUBLISHED, ScheduleVersionState.SUPERSEDED),
)
_EXPORT_JOB_TRANSITIONS = _pairs(
    (ExportJobState.CREATED, ExportJobState.EXPORTING),
    (ExportJobState.CREATED, ExportJobState.CANCELLED),
    (ExportJobState.EXPORTING, ExportJobState.EXPORTED),
    (ExportJobState.EXPORTING, ExportJobState.EXPORT_FAILED),
    (ExportJobState.EXPORTING, ExportJobState.CANCELLED),
    (ExportJobState.EXPORT_FAILED, ExportJobState.EXPORTING),
)

_STATES: Mapping[StateMachineName, frozenset[str]] = MappingProxyType(
    {
        StateMachineName.PLANNING_RUN: frozenset(state.value for state in PlanningRunState),
        StateMachineName.SCHEDULE_VERSION: frozenset(
            state.value for state in ScheduleVersionState
        ),
        StateMachineName.EXPORT_JOB: frozenset(state.value for state in ExportJobState),
    }
)
_TERMINAL_STATES: Mapping[StateMachineName, frozenset[str]] = MappingProxyType(
    {
        StateMachineName.PLANNING_RUN: frozenset(
            {
                PlanningRunState.COMPLETED.value,
                PlanningRunState.DATA_REJECTED.value,
                PlanningRunState.MODEL_INVALID.value,
                PlanningRunState.INFEASIBLE.value,
                PlanningRunState.NO_SOLUTION_WITHIN_LIMIT.value,
                PlanningRunState.VALIDATION_FAILED.value,
                PlanningRunState.CANCELLED.value,
                PlanningRunState.FAILED.value,
            }
        ),
        StateMachineName.SCHEDULE_VERSION: frozenset(
            {ScheduleVersionState.SUPERSEDED.value, ScheduleVersionState.REJECTED.value}
        ),
        StateMachineName.EXPORT_JOB: frozenset(
            {ExportJobState.EXPORTED.value, ExportJobState.CANCELLED.value}
        ),
    }
)
_TRANSITIONS: Mapping[StateMachineName, frozenset[tuple[str, str]]] = MappingProxyType(
    {
        StateMachineName.PLANNING_RUN: _PLANNING_RUN_TRANSITIONS,
        StateMachineName.SCHEDULE_VERSION: _SCHEDULE_VERSION_TRANSITIONS,
        StateMachineName.EXPORT_JOB: _EXPORT_JOB_TRANSITIONS,
    }
)


class StateTransitionError(ValueError):
    """A requested transition is not present in the versioned transition table."""

    code = ProductErrorCode.INVALID_STATE_TRANSITION
    category: ProductErrorCategory = category_for_error_code(code)

    def __init__(self, machine: str, source: str, target: str) -> None:
        self.machine = machine
        self.source = source
        self.target = target
        super().__init__(f"{self.code.value}: {machine} {source} -> {target}")


def _machine(value: StateMachineName | str) -> StateMachineName:
    try:
        return StateMachineName(value)
    except ValueError as error:
        raise StateTransitionError(str(value), "<unknown>", "<unknown>") from error


def states_for(machine: StateMachineName | str) -> frozenset[str]:
    return _STATES[_machine(machine)]


def terminal_states_for(machine: StateMachineName | str) -> frozenset[str]:
    return _TERMINAL_STATES[_machine(machine)]


def transitions_for(
    machine: StateMachineName | str,
) -> frozenset[tuple[str, str]]:
    return _TRANSITIONS[_machine(machine)]


def is_transition_allowed(
    machine: StateMachineName | str, source: str, target: str
) -> bool:
    try:
        selected = _machine(machine)
    except StateTransitionError:
        return False
    return source in _STATES[selected] and target in _STATES[selected] and (
        source,
        target,
    ) in _TRANSITIONS[selected]


def require_transition(
    machine: StateMachineName | str, source: str, target: str
) -> None:
    selected = _machine(machine)
    if not is_transition_allowed(selected, source, target):
        raise StateTransitionError(selected.value, source, target)


__all__ = [
    "ExportJobState",
    "PlanningRunState",
    "ScheduleVersionState",
    "StateMachineName",
    "StateTransitionDocument",
    "StateTransitionError",
    "is_transition_allowed",
    "require_transition",
    "states_for",
    "terminal_states_for",
    "transitions_for",
]
