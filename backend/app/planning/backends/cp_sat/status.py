"""Explicit OR-Tools CP-SAT to PlantNexus status mapping."""

from __future__ import annotations

from typing import TypedDict

from ortools.sat.python import cp_model

from app.planning.backends.contracts import (
    BackendFailureReason,
    SolverBackendError,
)
from app.planning.contracts import SolverStatus


class NativeStatusMappingDocument(TypedDict):
    native_name: str
    native_code: int
    solver_status: str


_NATIVE_STATUS_ROWS = (
    (cp_model.UNKNOWN, "UNKNOWN", SolverStatus.UNKNOWN),
    (cp_model.MODEL_INVALID, "MODEL_INVALID", SolverStatus.MODEL_INVALID),
    (cp_model.FEASIBLE, "FEASIBLE", SolverStatus.FEASIBLE),
    (cp_model.INFEASIBLE, "INFEASIBLE", SolverStatus.INFEASIBLE),
    (cp_model.OPTIMAL, "OPTIMAL", SolverStatus.OPTIMAL),
)
_STATUS_BY_CODE = {
    int(native_status.value): solver_status
    for native_status, _, solver_status in _NATIVE_STATUS_ROWS
}
_NAME_BY_CODE = {
    int(native_status.value): native_name
    for native_status, native_name, _ in _NATIVE_STATUS_ROWS
}


def _status_code(status: cp_model.CpSolverStatus | int) -> int:
    if isinstance(status, int):
        return status
    return int(status.value)


def solver_status_from_cp_sat(
    status: cp_model.CpSolverStatus | int,
    *,
    cancelled: bool = False,
) -> SolverStatus:
    """Map a native status without relying on the v9.15 ``status_name`` API."""

    if cancelled:
        return SolverStatus.CANCELLED
    code = _status_code(status)
    try:
        return _STATUS_BY_CODE[code]
    except KeyError as error:
        raise SolverBackendError(
            BackendFailureReason.UNSUPPORTED_NATIVE_STATUS,
            solver_status=SolverStatus.FAILED,
            message="Pinned CP-SAT returned an unregistered native status",
        ) from error


def native_status_name(status: cp_model.CpSolverStatus | int) -> str:
    """Return the registered native name without calling ``status_name``."""

    code = _status_code(status)
    try:
        return _NAME_BY_CODE[code]
    except KeyError as error:
        raise SolverBackendError(
            BackendFailureReason.UNSUPPORTED_NATIVE_STATUS,
            solver_status=SolverStatus.FAILED,
            message="Pinned CP-SAT returned an unregistered native status",
        ) from error


def native_status_contract() -> tuple[NativeStatusMappingDocument, ...]:
    """Return the complete, stable five-status native mapping."""

    return tuple(
        {
            "native_name": native_name,
            "native_code": int(native_status.value),
            "solver_status": solver_status.value,
        }
        for native_status, native_name, solver_status in _NATIVE_STATUS_ROWS
    )


__all__ = [
    "NativeStatusMappingDocument",
    "native_status_contract",
    "native_status_name",
    "solver_status_from_cp_sat",
]
