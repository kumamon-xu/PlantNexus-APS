"""Solver-independent PlanningSnapshot JSON contract types."""

from __future__ import annotations

from typing import Literal, NotRequired, TypedDict


class PlanningSnapshotDocument(TypedDict):
    snapshot_version: Literal["planning-snapshot.v1"]
    snapshot_id: str
    cutoff_at: str
    source_versions: dict[str, str]
    rule_version: str
    snapshot_hash: str
    entity_counts: dict[str, int]
    synthetic: bool
    scenario_id: NotRequired[str]


__all__ = ["PlanningSnapshotDocument"]
