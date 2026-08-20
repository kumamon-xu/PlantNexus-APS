"""Solver-neutral public contracts shared by planning backend adapters."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal, TypedDict

from app.planning.contracts import DiagnosticDocument, SolverBackend, SolverStatus


class BackendFailureReason(StrEnum):
    """Stable, sanitized adapter failure reasons."""

    VERSION_MISMATCH = "VERSION_MISMATCH"
    INVALID_PARAMETERS = "INVALID_PARAMETERS"
    UNSUPPORTED_NATIVE_STATUS = "UNSUPPORTED_NATIVE_STATUS"
    MODEL_BUILDER_NOT_IMPLEMENTED = "MODEL_BUILDER_NOT_IMPLEMENTED"
    ADAPTER_FAILURE = "ADAPTER_FAILURE"


class SolverBackendError(RuntimeError):
    """A backend-boundary failure that carries a stable product status."""

    code = "SOLVER_BACKEND_ERROR"

    def __init__(
        self,
        reason: BackendFailureReason,
        *,
        solver_status: SolverStatus,
        message: str,
    ) -> None:
        self.reason = reason
        self.solver_status = solver_status
        self.message = message
        super().__init__(f"{self.code}/{reason.value}: {message}")

    def diagnostic(self) -> DiagnosticDocument:
        """Return a JSON-compatible diagnostic without native exception detail."""

        return {
            "code": f"{self.code}_{self.reason.value}",
            "message": self.message,
        }


class BackendIdentityDocument(TypedDict):
    backend_id: str
    backend_version: str
    solver_name: str
    solver_version: str


class BackendModelMetricsDocument(TypedDict):
    variables: int
    constraints: int
    optional_intervals: int


class BackendSmokeResultDocument(TypedDict):
    smoke_kind: Literal["EMPTY_MODEL", "MODEL_INVALID"]
    native_status: str
    solver_status: str
    business_feasibility: Literal["NOT_EVALUATED"]
    candidate_produced: Literal[False]
    model_metrics: BackendModelMetricsDocument
    wall_time_seconds: float
    diagnostics: list[DiagnosticDocument]


__all__ = [
    "BackendFailureReason",
    "BackendIdentityDocument",
    "BackendModelMetricsDocument",
    "BackendSmokeResultDocument",
    "SolverBackend",
    "SolverBackendError",
]
