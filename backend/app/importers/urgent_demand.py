"""Standard-ingress input carrier for one urgent-demand ExecutionEvent.

This value does not accept a prebuilt canonical document.  Callers must supply
the same Raw Staging + MappingProfile inputs used by P1 normalization.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.normalization.contracts import NormalizationInput

from .contracts import ImportStagingError, StagingDataPlane, StagingErrorCode


@dataclass(frozen=True, slots=True)
class UrgentDemandImport:
    """Complete standard-import inputs bound to one immutable event identity."""

    event_id: str
    inputs: tuple[NormalizationInput, ...]

    def __post_init__(self) -> None:
        if not self.event_id.startswith("execution-event-") or len(self.event_id) != 80:
            raise ImportStagingError(
                StagingErrorCode.INVALID_STAGING_METADATA,
                "urgent demand event_id must use the execution-event SHA-256 namespace",
            )
        if not self.inputs:
            raise ImportStagingError(
                StagingErrorCode.INVALID_STAGING_METADATA,
                "urgent demand requires complete standard normalization inputs",
            )
        if any(
            item.batch.data_plane is not StagingDataPlane.SIMULATION
            for item in self.inputs
        ):
            raise ImportStagingError(
                StagingErrorCode.DATA_PLANE_MISMATCH,
                "urgent demand standard import is Simulation-only in P4",
            )


__all__ = ["UrgentDemandImport"]
