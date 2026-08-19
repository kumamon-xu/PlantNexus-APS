"""Immutable, solver-independent PlanningSnapshot contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import json
from typing import Literal, NotRequired, TypedDict, cast

from app.domain.canonical_records import PlanningSnapshotDocumentV2


class PlanningSnapshotDocument(TypedDict):
    """Retained P0 v1 skeleton; v1 is not reinterpreted as v2."""

    snapshot_version: Literal["planning-snapshot.v1"]
    snapshot_id: str
    cutoff_at: str
    source_versions: dict[str, str]
    rule_version: str
    snapshot_hash: str
    entity_counts: dict[str, int]
    synthetic: bool
    scenario_id: NotRequired[str]


class SnapshotDataPlane(StrEnum):
    """The two isolated persistence planes for immutable Snapshots."""

    PRODUCTION = "production"
    SIMULATION = "simulation"


class SnapshotErrorCode(StrEnum):
    """Stable module-local rejection codes for the Snapshot boundary."""

    INVALID_SNAPSHOT_INPUT = "INVALID_SNAPSHOT_INPUT"
    QUALITY_REPORT_REQUIRED = "QUALITY_REPORT_REQUIRED"
    SNAPSHOT_INPUT_MISMATCH = "SNAPSHOT_INPUT_MISMATCH"
    HASH_MISMATCH = "HASH_MISMATCH"
    DATA_PLANE_MISMATCH = "DATA_PLANE_MISMATCH"
    CONTENT_CONFLICT = "CONTENT_CONFLICT"
    IMMUTABLE_SNAPSHOT = "IMMUTABLE_SNAPSHOT"
    SNAPSHOT_PERSISTENCE_FAILED = "SNAPSHOT_PERSISTENCE_FAILED"


class SnapshotError(ValueError):
    """A deterministic, sanitized Snapshot rejection."""

    def __init__(
        self,
        code: SnapshotErrorCode,
        *,
        field: str,
        expected_contract: str,
        message: str,
    ) -> None:
        self.code = code
        self.field = field
        self.expected_contract = expected_contract
        self.message = message
        super().__init__(f"{code.value} at {field}: {message}")


@dataclass(frozen=True)
class ImmutablePlanningSnapshot:
    """A Snapshot value backed only by immutable canonical bytes.

    ``document`` returns a new JSON-compatible object on every access, so a
    caller cannot mutate the authoritative bytes retained by this value.
    """

    canonical_bytes: bytes
    snapshot_id: str
    snapshot_hash: str
    data_plane: SnapshotDataPlane

    @property
    def document(self) -> PlanningSnapshotDocumentV2:
        decoded = json.loads(self.canonical_bytes)
        return cast(PlanningSnapshotDocumentV2, decoded)


@dataclass(frozen=True)
class SnapshotWriteResult:
    snapshot: ImmutablePlanningSnapshot
    replayed: bool


__all__ = [
    "ImmutablePlanningSnapshot",
    "PlanningSnapshotDocument",
    "PlanningSnapshotDocumentV2",
    "SnapshotDataPlane",
    "SnapshotError",
    "SnapshotErrorCode",
    "SnapshotWriteResult",
]
