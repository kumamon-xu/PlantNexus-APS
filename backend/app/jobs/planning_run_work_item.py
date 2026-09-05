"""Deterministic queue-ready PlanningRun attempt records.

No broker call or Solver invocation occurs here.  P8-05 may deliver these
immutable work items and advance their separately persisted attempt record.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from app.data_validation.canonical_ingress import (
    canonical_fingerprint,
    canonical_json_bytes,
)
from app.domain.planning_run import (
    PLANNING_RUN_ATTEMPT_VERSION,
    PLANNING_RUN_WORK_ITEM_VERSION,
    PlanningRunAggregate,
    PlanningRunAttempt,
    PlanningRunAttemptStatus,
    PlanningRunWorkItem,
    derived_identity,
    verify_attempt,
    verify_work_item,
)


type JsonObject = dict[str, Any]


def _with_fingerprint(document: JsonObject, field: str) -> JsonObject:
    result = {**document, field: ""}
    result[field] = canonical_fingerprint(
        {key: value for key, value in result.items() if key != field}
    )
    return result


def _extension_set_fingerprint(runtime: Mapping[str, object]) -> str:
    extension_set = runtime.get("extension_set")
    if not isinstance(extension_set, Mapping) or not isinstance(
        extension_set.get("extension_set_fingerprint"), str
    ):
        raise ValueError("Runtime extension-set fingerprint is absent")
    return cast(str, extension_set["extension_set_fingerprint"])


def create_queued_attempt(
    aggregate: PlanningRunAggregate,
    *,
    attempt_number: int,
    available_at_utc: str,
    timeout_at_utc: str,
    audit_reference: Mapping[str, object],
) -> PlanningRunAttempt:
    """Create one immutable attempt identity in QUEUED diagnostic state."""

    run = aggregate.document
    runtime = cast(Mapping[str, object], run["runtime_resolution"])
    seed = {
        "planning_run_id": run["planning_run_id"],
        "attempt_number": attempt_number,
        "expected_run_fingerprint": run["run_fingerprint"],
    }
    document = _with_fingerprint(
        {
            "attempt_version": PLANNING_RUN_ATTEMPT_VERSION,
            "attempt_id": derived_identity("planning-run-attempt", seed),
            "planning_run_id": run["planning_run_id"],
            "attempt_number": attempt_number,
            "revision": 1,
            "status": PlanningRunAttemptStatus.QUEUED.value,
            "expected_run_revision": run["revision"],
            "expected_run_state": run["state"],
            "expected_run_fingerprint": run["run_fingerprint"],
            "runtime_resolution_fingerprint": runtime["resolution_fingerprint"],
            "extension_set_fingerprint": _extension_set_fingerprint(runtime),
            "available_at_utc": available_at_utc,
            "timeout_at_utc": timeout_at_utc,
            "started_at_utc": None,
            "finished_at_utc": None,
            "failure_code": None,
            "result_references": run["artifacts"],
            "audit": dict(audit_reference),
        },
        "attempt_fingerprint",
    )
    attempt = PlanningRunAttempt(canonical_json_bytes(document))
    verify_attempt(attempt, aggregate=aggregate)
    return attempt


def create_work_item(
    aggregate: PlanningRunAggregate,
    *,
    attempt: PlanningRunAttempt,
    correlation_id: str,
) -> PlanningRunWorkItem:
    """Freeze all worker inputs without accepting executable client fields."""

    run = aggregate.document
    attempt_document = attempt.document
    seed = {
        "planning_run_id": run["planning_run_id"],
        "attempt_id": attempt_document["attempt_id"],
        "attempt_number": attempt_document["attempt_number"],
    }
    document = _with_fingerprint(
        {
            "work_item_version": PLANNING_RUN_WORK_ITEM_VERSION,
            "work_item_id": derived_identity("planning-run-work-item", seed),
            "planning_run_id": run["planning_run_id"],
            "attempt_id": attempt_document["attempt_id"],
            "attempt_number": attempt_document["attempt_number"],
            "expected_run_revision": attempt_document["expected_run_revision"],
            "expected_run_state": attempt_document["expected_run_state"],
            "expected_run_fingerprint": attempt_document["expected_run_fingerprint"],
            "runtime_resolution": run["runtime_resolution"],
            "prepared_artifacts": aggregate.prepared_artifacts,
            "inputs": run["inputs"],
            "available_at_utc": attempt_document["available_at_utc"],
            "timeout_at_utc": attempt_document["timeout_at_utc"],
            "correlation_id": correlation_id,
            "audit": attempt_document["audit"],
        },
        "work_item_fingerprint",
    )
    work_item = PlanningRunWorkItem(canonical_json_bytes(document))
    verify_work_item(work_item, aggregate=aggregate, attempt=attempt)
    return work_item


def transition_attempt(
    attempt: PlanningRunAttempt,
    *,
    aggregate: PlanningRunAggregate,
    to_status: PlanningRunAttemptStatus,
    occurred_at_utc: str,
    audit_reference: Mapping[str, object],
    failure_code: str | None,
    result_references: Mapping[str, object],
) -> PlanningRunAttempt:
    """Advance one attempt by a frozen operational pair and one CAS revision."""

    previous = attempt.document
    started = previous["started_at_utc"]
    if to_status is PlanningRunAttemptStatus.ACTIVE and started is None:
        started = occurred_at_utc
    finished = previous["finished_at_utc"]
    if to_status in {
        PlanningRunAttemptStatus.DISPATCH_FAILED,
        PlanningRunAttemptStatus.TIMED_OUT,
        PlanningRunAttemptStatus.CANCELLED,
        PlanningRunAttemptStatus.SUCCEEDED,
        PlanningRunAttemptStatus.FAILED,
    }:
        finished = occurred_at_utc
    document = _with_fingerprint(
        {
            **previous,
            "revision": cast(int, previous["revision"]) + 1,
            "status": to_status.value,
            "started_at_utc": started,
            "finished_at_utc": finished,
            "failure_code": failure_code,
            "result_references": dict(result_references),
            "audit": dict(audit_reference),
        },
        "attempt_fingerprint",
    )
    result = PlanningRunAttempt(canonical_json_bytes(document))
    verify_attempt(result, aggregate=aggregate, previous=previous)
    return result


__all__ = [
    "create_queued_attempt",
    "create_work_item",
    "transition_attempt",
]
