"""Immutable domain value and fail-closed errors for P4 ChangeReport."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import json
from typing import NoReturn, cast


type JsonObject = dict[str, object]


class ChangeReportFailure(StrEnum):
    """Stable local failures without extending the product error registry."""

    INVALID_INPUT = "INVALID_INPUT"
    INVALID_ASSIGNMENT = "INVALID_ASSIGNMENT"
    DUPLICATE_OPERATION = "DUPLICATE_OPERATION"
    ACTIVE_UNIVERSE_MISMATCH = "ACTIVE_UNIVERSE_MISMATCH"
    MISSING_FACT_EVIDENCE = "MISSING_FACT_EVIDENCE"
    INVALID_REASON_EVIDENCE = "INVALID_REASON_EVIDENCE"
    KPI_EVIDENCE_MISMATCH = "KPI_EVIDENCE_MISMATCH"
    LINEAGE_MISMATCH = "LINEAGE_MISMATCH"
    PLANE_MISMATCH = "PLANE_MISMATCH"
    CONTRACT_REJECTED = "CONTRACT_REJECTED"


class ChangeReportError(ValueError):
    """Reject invalid inputs before persistence, Solver, or Version side effects."""

    def __init__(
        self,
        reason: ChangeReportFailure,
        *,
        field: str,
        entity_id: str,
        message: str,
    ) -> None:
        self.reason = reason
        self.field = field
        self.entity_id = entity_id
        self.message = message
        super().__init__(f"{reason.value} at {field} ({entity_id}): {message}")


def reject_change_report(
    reason: ChangeReportFailure,
    *,
    field: str,
    entity_id: str,
    message: str,
) -> NoReturn:
    """Raise the shared structured P4-06 input error."""

    raise ChangeReportError(
        reason,
        field=field,
        entity_id=entity_id,
        message=message,
    )


@dataclass(frozen=True, slots=True)
class ImmutableChangeReport:
    """Canonical immutable ChangeReport bytes and content identity."""

    canonical_bytes: bytes
    report_id: str
    report_fingerprint: str

    @property
    def document(self) -> JsonObject:
        return cast(JsonObject, json.loads(self.canonical_bytes))


__all__ = [
    "ChangeReportError",
    "ChangeReportFailure",
    "ImmutableChangeReport",
    "reject_change_report",
]
