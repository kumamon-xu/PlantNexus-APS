"""Internal immutable contracts for the P8 asynchronous Solver Worker.

These carriers are deliberately not public API Schemas.  They bind one
durable work item to the exact Solver/Validator output needed to reconcile a
PlanningRun and the existing ScheduleVersion application after a crash.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
import json
import re
from typing import Any, NoReturn, cast

from app.data_validation.canonical_ingress import (
    canonical_fingerprint,
    canonical_json_bytes,
)
from app.domain.planning_run import derived_identity


type JsonObject = dict[str, Any]

PLANNING_RUN_WORKER_RESULT_VERSION = "planning-run-worker-result.v1"
PLANNING_RUN_SOLVER_JOB_KIND = "P8_PLANNING_RUN_SOLVER"

_FINGERPRINT = re.compile(r"sha256:[0-9a-f]{64}")
_DIGEST = re.compile(r"[0-9a-f]{64}")
_ARTIFACT_FIELDS = {
    "import_quality_report",
    "snapshot",
    "problem",
    "planning_solution",
    "solver_report",
    "validation_report",
    "schedule_version",
}
_RESULT_FIELDS = {
    "worker_result_version",
    "result_id",
    "job_id",
    "planning_run_id",
    "attempt_id",
    "work_item_id",
    "data_plane",
    "work_item_fingerprint",
    "runtime_resolution_fingerprint",
    "outcome_state",
    "artifact_references",
    "documents",
    "schedule_context",
    "schedule_version_reference",
    "created_at_utc",
    "result_fingerprint",
}
_DOCUMENT_FIELDS = {
    "planning_solution",
    "solver_report",
    "validation_report",
    "kpi",
}
_OUTCOMES = {
    "COMPLETED",
    "MODEL_INVALID",
    "INFEASIBLE",
    "NO_SOLUTION_WITHIN_LIMIT",
    "VALIDATION_FAILED",
    "CANCELLED",
    "FAILED",
}


class PlanningRunWorkerErrorCode(StrEnum):
    INVALID_MESSAGE = "INVALID_MESSAGE"
    INVALID_WORK_ITEM = "INVALID_WORK_ITEM"
    INPUT_MISMATCH = "INPUT_MISMATCH"
    RUNTIME_MISMATCH = "RUNTIME_MISMATCH"
    NOT_AVAILABLE = "NOT_AVAILABLE"
    LEASE_BUSY = "LEASE_BUSY"
    LEASE_LOST = "LEASE_LOST"
    ATTEMPT_TIMED_OUT = "ATTEMPT_TIMED_OUT"
    RUN_CANCELLED = "RUN_CANCELLED"
    RESULT_CONFLICT = "RESULT_CONFLICT"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    PERSISTENCE_FAILED = "PERSISTENCE_FAILED"
    EXECUTION_FAILED = "EXECUTION_FAILED"


class PlanningRunWorkerError(RuntimeError):
    """Sanitized worker failure; values and infrastructure details stay hidden."""

    def __init__(
        self,
        code: PlanningRunWorkerErrorCode,
        *,
        field: str,
        message: str,
        retryable: bool = False,
    ) -> None:
        self.code = code
        self.field = field
        self.message = message
        self.retryable = retryable
        super().__init__(f"{code.value}: {field}: {message}")


def reject_worker(
    code: PlanningRunWorkerErrorCode,
    *,
    field: str,
    message: str,
    retryable: bool = False,
) -> NoReturn:
    raise PlanningRunWorkerError(
        code, field=field, message=message, retryable=retryable
    )


@dataclass(frozen=True, slots=True)
class PlanningRunResolvedInputs:
    """Server-resolved immutable input documents for one work item."""

    import_quality_report: Mapping[str, object]
    snapshot: Mapping[str, object]
    problem: Mapping[str, object]
    planning_policy: Mapping[str, object]
    solve_limits: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class PlanningRunWorkerResult:
    """Canonical immutable checkpoint stored before terminal reconciliation."""

    canonical_bytes: bytes

    @property
    def document(self) -> JsonObject:
        try:
            value = json.loads(self.canonical_bytes)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise PlanningRunWorkerError(
                PlanningRunWorkerErrorCode.RESULT_CONFLICT,
                field="worker_result",
                message="Worker result checkpoint is unreadable",
            ) from error
        if (
            not isinstance(value, dict)
            or canonical_json_bytes(value) != self.canonical_bytes
        ):
            reject_worker(
                PlanningRunWorkerErrorCode.RESULT_CONFLICT,
                field="worker_result",
                message="Worker result checkpoint is not canonical JSON",
            )
        return cast(JsonObject, value)


def _require_fingerprint(value: object, field: str) -> str:
    if not isinstance(value, str) or _FINGERPRINT.fullmatch(value) is None:
        reject_worker(
            PlanningRunWorkerErrorCode.RESULT_CONFLICT,
            field=field,
            message="Expected a lowercase SHA-256 fingerprint",
        )
    return value


def _require_utc(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.endswith("Z"):
        reject_worker(
            PlanningRunWorkerErrorCode.RESULT_CONFLICT,
            field=field,
            message="Expected an explicit UTC instant",
        )
    try:
        datetime.fromisoformat(value.removesuffix("Z") + "+00:00")
    except ValueError as error:
        raise PlanningRunWorkerError(
            PlanningRunWorkerErrorCode.RESULT_CONFLICT,
            field=field,
            message="Expected a valid UTC instant",
        ) from error
    return value


def worker_job_identity(
    work_item: Mapping[str, object], *, data_plane: str
) -> tuple[str, str, str]:
    """Return deterministic job ID, key reference, and request digest."""

    basis = {
        "job_kind": PLANNING_RUN_SOLVER_JOB_KIND,
        "data_plane": data_plane,
        "planning_run_id": work_item.get("planning_run_id"),
        "attempt_id": work_item.get("attempt_id"),
        "work_item_id": work_item.get("work_item_id"),
        "work_item_fingerprint": work_item.get("work_item_fingerprint"),
    }
    fingerprint = canonical_fingerprint(basis)
    digest = fingerprint.removeprefix("sha256:")
    key_reference = canonical_fingerprint(
        {"scope": PLANNING_RUN_SOLVER_JOB_KIND, "work_item_id": basis["work_item_id"]}
    )
    return digest, key_reference, digest


def build_worker_result(
    *,
    job_id: str,
    data_plane: str,
    work_item: Mapping[str, object],
    outcome_state: str,
    artifact_references: Mapping[str, object],
    planning_solution: Mapping[str, object] | None,
    solver_report: Mapping[str, object] | None,
    validation_report: Mapping[str, object] | None,
    kpi: Mapping[str, object] | None,
    schedule_context: Mapping[str, object] | None,
    schedule_version_reference: Mapping[str, object] | None,
    created_at_utc: str,
) -> PlanningRunWorkerResult:
    """Freeze the exact output used by every later idempotent reconciliation."""

    result_id = derived_identity(
        "planning-run-worker-result",
        {
            "job_id": job_id,
            "attempt_id": work_item.get("attempt_id"),
            "work_item_fingerprint": work_item.get("work_item_fingerprint"),
        },
    )
    runtime = work_item.get("runtime_resolution")
    if not isinstance(runtime, Mapping):
        reject_worker(
            PlanningRunWorkerErrorCode.INVALID_WORK_ITEM,
            field="work_item.runtime_resolution",
            message="Work item has no Runtime resolution",
        )
    document: JsonObject = {
        "worker_result_version": PLANNING_RUN_WORKER_RESULT_VERSION,
        "result_id": result_id,
        "job_id": job_id,
        "planning_run_id": work_item.get("planning_run_id"),
        "attempt_id": work_item.get("attempt_id"),
        "work_item_id": work_item.get("work_item_id"),
        "data_plane": data_plane,
        "work_item_fingerprint": work_item.get("work_item_fingerprint"),
        "runtime_resolution_fingerprint": runtime.get("resolution_fingerprint"),
        "outcome_state": outcome_state,
        "artifact_references": dict(artifact_references),
        "documents": {
            "planning_solution": (
                None if planning_solution is None else dict(planning_solution)
            ),
            "solver_report": None if solver_report is None else dict(solver_report),
            "validation_report": (
                None if validation_report is None else dict(validation_report)
            ),
            "kpi": None if kpi is None else dict(kpi),
        },
        "schedule_context": (
            None if schedule_context is None else dict(schedule_context)
        ),
        "schedule_version_reference": (
            None
            if schedule_version_reference is None
            else dict(schedule_version_reference)
        ),
        "created_at_utc": created_at_utc,
        "result_fingerprint": "",
    }
    document["result_fingerprint"] = canonical_fingerprint(
        {key: value for key, value in document.items() if key != "result_fingerprint"}
    )
    result = PlanningRunWorkerResult(canonical_json_bytes(document))
    verify_worker_result(result, expected_work_item=work_item, data_plane=data_plane)
    return result


def verify_worker_result(
    result: PlanningRunWorkerResult,
    *,
    expected_work_item: Mapping[str, object] | None = None,
    data_plane: str | None = None,
) -> None:
    document = result.document
    if set(document) != _RESULT_FIELDS:
        reject_worker(
            PlanningRunWorkerErrorCode.RESULT_CONFLICT,
            field="worker_result",
            message="Worker result field set is invalid",
        )
    if document.get("worker_result_version") != PLANNING_RUN_WORKER_RESULT_VERSION:
        reject_worker(
            PlanningRunWorkerErrorCode.RESULT_CONFLICT,
            field="worker_result.worker_result_version",
            message="Worker result version is unsupported",
        )
    for field in ("result_id", "planning_run_id", "attempt_id", "work_item_id"):
        if not isinstance(document.get(field), str) or not document[field]:
            reject_worker(
                PlanningRunWorkerErrorCode.RESULT_CONFLICT,
                field=f"worker_result.{field}",
                message="Worker result identity is invalid",
            )
    if (
        not isinstance(document.get("job_id"), str)
        or _DIGEST.fullmatch(cast(str, document["job_id"])) is None
    ):
        reject_worker(
            PlanningRunWorkerErrorCode.RESULT_CONFLICT,
            field="worker_result.job_id",
            message="Worker job identity is invalid",
        )
    if document.get("data_plane") not in {"SIMULATION", "PRODUCTION"}:
        reject_worker(
            PlanningRunWorkerErrorCode.RESULT_CONFLICT,
            field="worker_result.data_plane",
            message="Worker result data plane is invalid",
        )
    if data_plane is not None and document.get("data_plane") != data_plane:
        reject_worker(
            PlanningRunWorkerErrorCode.RESULT_CONFLICT,
            field="worker_result.data_plane",
            message="Worker result crossed its repository data plane",
        )
    _require_fingerprint(
        document.get("work_item_fingerprint"),
        "worker_result.work_item_fingerprint",
    )
    _require_fingerprint(
        document.get("runtime_resolution_fingerprint"),
        "worker_result.runtime_resolution_fingerprint",
    )
    _require_fingerprint(
        document.get("result_fingerprint"), "worker_result.result_fingerprint"
    )
    if document.get("result_fingerprint") != canonical_fingerprint(
        {key: value for key, value in document.items() if key != "result_fingerprint"}
    ):
        reject_worker(
            PlanningRunWorkerErrorCode.RESULT_CONFLICT,
            field="worker_result.result_fingerprint",
            message="Worker result fingerprint is invalid",
        )
    _require_utc(document.get("created_at_utc"), "worker_result.created_at_utc")
    outcome = document.get("outcome_state")
    if outcome not in _OUTCOMES:
        reject_worker(
            PlanningRunWorkerErrorCode.RESULT_CONFLICT,
            field="worker_result.outcome_state",
            message="Worker result outcome is unsupported",
        )
    artifacts = document.get("artifact_references")
    documents = document.get("documents")
    if not isinstance(artifacts, Mapping) or set(artifacts) != _ARTIFACT_FIELDS:
        reject_worker(
            PlanningRunWorkerErrorCode.RESULT_CONFLICT,
            field="worker_result.artifact_references",
            message="Worker artifact reference set is invalid",
        )
    if not isinstance(documents, Mapping) or set(documents) != _DOCUMENT_FIELDS:
        reject_worker(
            PlanningRunWorkerErrorCode.RESULT_CONFLICT,
            field="worker_result.documents",
            message="Worker document set is invalid",
        )
    for field, value in documents.items():
        if value is not None and not isinstance(value, Mapping):
            reject_worker(
                PlanningRunWorkerErrorCode.RESULT_CONFLICT,
                field=f"worker_result.documents.{field}",
                message="Worker output document is invalid",
            )
    for field, value in artifacts.items():
        if value is not None and not isinstance(value, Mapping):
            reject_worker(
                PlanningRunWorkerErrorCode.RESULT_CONFLICT,
                field=f"worker_result.artifact_references.{field}",
                message="Worker artifact reference is invalid",
            )
    if document.get("schedule_context") is not None and not isinstance(
        document["schedule_context"], Mapping
    ):
        reject_worker(
            PlanningRunWorkerErrorCode.RESULT_CONFLICT,
            field="worker_result.schedule_context",
            message="Worker ScheduleVersion context is invalid",
        )
    if document.get("schedule_version_reference") is not None and not isinstance(
        document["schedule_version_reference"], Mapping
    ):
        reject_worker(
            PlanningRunWorkerErrorCode.RESULT_CONFLICT,
            field="worker_result.schedule_version_reference",
            message="Worker ScheduleVersion reference is invalid",
        )
    if any(
        artifacts.get(name) is None
        for name in ("import_quality_report", "snapshot", "problem", "solver_report")
    ) or any(
        documents.get(name) is None for name in ("planning_solution", "solver_report")
    ):
        reject_worker(
            PlanningRunWorkerErrorCode.RESULT_CONFLICT,
            field="worker_result.artifact_references",
            message="Worker result lacks required Solver lineage",
        )
    if outcome == "COMPLETED":
        if any(documents.get(name) is None for name in _DOCUMENT_FIELDS):
            reject_worker(
                PlanningRunWorkerErrorCode.RESULT_CONFLICT,
                field="worker_result.documents",
                message="Completed Worker result lacks validated output",
            )
        if (
            document.get("schedule_context") is None
            or document.get("schedule_version_reference") is None
        ):
            reject_worker(
                PlanningRunWorkerErrorCode.RESULT_CONFLICT,
                field="worker_result.schedule_version_reference",
                message="Completed Worker result lacks ScheduleVersion evidence",
            )
        if any(artifacts.get(name) is None for name in _ARTIFACT_FIELDS):
            reject_worker(
                PlanningRunWorkerErrorCode.RESULT_CONFLICT,
                field="worker_result.artifact_references",
                message="Completed Worker result lacks a published reference",
            )
    elif outcome == "VALIDATION_FAILED":
        if (
            documents.get("validation_report") is None
            or documents.get("kpi") is not None
            or artifacts.get("planning_solution") is None
            or artifacts.get("validation_report") is None
        ):
            reject_worker(
                PlanningRunWorkerErrorCode.RESULT_CONFLICT,
                field="worker_result.documents.validation_report",
                message="Validation failure result has inconsistent evidence",
            )
    elif (
        documents.get("validation_report") is not None
        or documents.get("kpi") is not None
        or artifacts.get("planning_solution") is not None
        or artifacts.get("validation_report") is not None
    ):
        reject_worker(
            PlanningRunWorkerErrorCode.RESULT_CONFLICT,
            field="worker_result.documents",
            message="Non-candidate Worker result has candidate-only evidence",
        )
    if outcome != "COMPLETED" and (
        document.get("schedule_context") is not None
        or document.get("schedule_version_reference") is not None
        or artifacts.get("schedule_version") is not None
    ):
        reject_worker(
            PlanningRunWorkerErrorCode.RESULT_CONFLICT,
            field="worker_result.schedule_version_reference",
            message="Non-completed Worker result cannot expose ScheduleVersion evidence",
        )
    if expected_work_item is not None:
        expected = {
            "planning_run_id": expected_work_item.get("planning_run_id"),
            "attempt_id": expected_work_item.get("attempt_id"),
            "work_item_id": expected_work_item.get("work_item_id"),
            "work_item_fingerprint": expected_work_item.get("work_item_fingerprint"),
        }
        if any(document.get(field) != value for field, value in expected.items()):
            reject_worker(
                PlanningRunWorkerErrorCode.RESULT_CONFLICT,
                field="worker_result.work_item",
                message="Worker result is bound to another work item",
            )
        runtime = expected_work_item.get("runtime_resolution")
        if not isinstance(runtime, Mapping) or document.get(
            "runtime_resolution_fingerprint"
        ) != runtime.get("resolution_fingerprint"):
            reject_worker(
                PlanningRunWorkerErrorCode.RESULT_CONFLICT,
                field="worker_result.runtime_resolution_fingerprint",
                message="Worker result Runtime binding differs from its work item",
            )
        expected_job_id, _, _ = worker_job_identity(
            expected_work_item,
            data_plane=cast(str, document["data_plane"]),
        )
        if document.get("job_id") != expected_job_id:
            reject_worker(
                PlanningRunWorkerErrorCode.RESULT_CONFLICT,
                field="worker_result.job_id",
                message="Worker result job identity is invalid",
            )


__all__ = [
    "PLANNING_RUN_SOLVER_JOB_KIND",
    "PLANNING_RUN_WORKER_RESULT_VERSION",
    "PlanningRunResolvedInputs",
    "PlanningRunWorkerError",
    "PlanningRunWorkerErrorCode",
    "PlanningRunWorkerResult",
    "build_worker_result",
    "reject_worker",
    "verify_worker_result",
    "worker_job_identity",
]
