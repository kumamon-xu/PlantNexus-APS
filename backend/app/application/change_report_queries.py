"""Versioned, read-only ChangeReport and replan-lineage projection for P4."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from enum import StrEnum
import json
import re
from typing import Never, Protocol, cast

from app.domain.execution_contracts import (
    canonical_contract_bytes,
    contract_fingerprint,
    require_p4_document,
)
from app.domain.types import parse_utc_instant


CHANGE_REPORT_READ_MODEL_VERSION = "change-report-read-model.v1"
_FINGERPRINT = re.compile(r"sha256:[0-9a-f]{64}")
_ACTOR = re.compile(r"actor:[A-Za-z0-9._:/-]+")
_CLASSIFICATIONS = frozenset({"UNCHANGED", "CHANGED", "ADDED", "REMOVED_BY_FACT"})


class ChangeReportReadFailure(StrEnum):
    INVALID_QUERY = "INVALID_QUERY"
    AUTHORIZATION_DENIED = "AUTHORIZATION_DENIED"
    PRODUCTION_AUTHORITY_UNAVAILABLE = "PRODUCTION_AUTHORITY_UNAVAILABLE"
    SOURCE_NOT_FOUND = "SOURCE_NOT_FOUND"
    LINEAGE_MISMATCH = "LINEAGE_MISMATCH"
    CONTRACT_REJECTED = "CONTRACT_REJECTED"
    PERSISTENCE_FAILED = "PERSISTENCE_FAILED"


class ChangeReportReadError(ValueError):
    def __init__(self, reason: ChangeReportReadFailure, *, field: str) -> None:
        self.reason = reason
        self.field = field
        super().__init__(f"{reason.value}: {field}")


@dataclass(frozen=True, slots=True)
class ChangeReportQuery:
    attempt_id: str
    expected_result_fingerprint: str
    expected_schedule_version_id: str
    expected_schedule_content_fingerprint: str
    expected_report_id: str
    expected_report_fingerprint: str
    classifications: tuple[str, ...] = ()
    operation_ids: tuple[str, ...] = ()
    after_operation_id: str | None = None
    limit: int = 100


@dataclass(frozen=True, slots=True)
class ChangeReportReadContext:
    actor_ref: str
    authenticated: bool
    resolved_capabilities: frozenset[str]
    attempt_scope: frozenset[str]
    schedule_version_scope: frozenset[str]
    data_plane: str
    environment: str
    production_binding: bool


class StoredAppliedResultPort(Protocol):
    @property
    def result(self) -> dict[str, object]: ...

    @property
    def solver_report(self) -> dict[str, object]: ...

    @property
    def validation_report(self) -> dict[str, object]: ...

    @property
    def kpi(self) -> dict[str, object]: ...

    @property
    def change_report(self) -> dict[str, object]: ...


class ChangeReportLineageRepositoryPort(Protocol):
    def get_applied_result_for_attempt(
        self, attempt_id: str
    ) -> StoredAppliedResultPort | None: ...


class ChangeReportScheduleRepositoryPort(Protocol):
    def get(self, schedule_version_id: str) -> dict[str, object] | None: ...


@dataclass(frozen=True, slots=True)
class ChangeReportReadResult:
    document: dict[str, object]
    change_report: dict[str, object]
    schedule_version: dict[str, object]


def _reject(reason: ChangeReportReadFailure, field: str) -> Never:
    raise ChangeReportReadError(reason, field=field)


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        _reject(ChangeReportReadFailure.INVALID_QUERY, field)
    return value


def _fingerprint(value: object, field: str) -> str:
    text = _text(value, field)
    if _FINGERPRINT.fullmatch(text) is None:
        _reject(ChangeReportReadFailure.INVALID_QUERY, field)
    return text


def _mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        _reject(ChangeReportReadFailure.LINEAGE_MISMATCH, field)
    return cast(Mapping[str, object], value)


def _reference(
    value: object,
    field: str,
    *,
    id_field: str = "artifact_id",
    fingerprint_field: str = "fingerprint",
) -> tuple[str, str]:
    reference = _mapping(value, field)
    identity = reference.get(id_field)
    fingerprint = reference.get(fingerprint_field)
    if not isinstance(identity, str) or not identity or not isinstance(fingerprint, str):
        _reject(ChangeReportReadFailure.LINEAGE_MISMATCH, field)
    return identity, fingerprint


def _validate_query(query: ChangeReportQuery) -> None:
    for field in (
        "attempt_id",
        "expected_schedule_version_id",
        "expected_report_id",
    ):
        _text(getattr(query, field), field)
    for field in (
        "expected_result_fingerprint",
        "expected_schedule_content_fingerprint",
        "expected_report_fingerprint",
    ):
        _fingerprint(getattr(query, field), field)
    if isinstance(query.limit, bool) or not 1 <= query.limit <= 200:
        _reject(ChangeReportReadFailure.INVALID_QUERY, "limit")
    if query.after_operation_id is not None:
        _text(query.after_operation_id, "after_operation_id")
    if tuple(sorted(set(query.classifications))) != query.classifications or any(
        value not in _CLASSIFICATIONS for value in query.classifications
    ):
        _reject(ChangeReportReadFailure.INVALID_QUERY, "classifications")
    if tuple(sorted(set(query.operation_ids))) != query.operation_ids or any(
        not isinstance(value, str) or not value for value in query.operation_ids
    ):
        _reject(ChangeReportReadFailure.INVALID_QUERY, "operation_ids")


def _authorize(query: ChangeReportQuery, context: ChangeReportReadContext) -> None:
    if context.data_plane == "PRODUCTION" or context.environment == "PRODUCTION":
        _reject(
            ChangeReportReadFailure.PRODUCTION_AUTHORITY_UNAVAILABLE,
            "data_plane/environment",
        )
    if (
        context.data_plane != "SIMULATION"
        or context.environment not in {"DEVELOPMENT", "TEST", "BENCHMARK"}
        or context.production_binding
        or not context.authenticated
        or _ACTOR.fullmatch(context.actor_ref) is None
        or "view" not in context.resolved_capabilities
        or query.attempt_id not in context.attempt_scope
        or query.expected_schedule_version_id not in context.schedule_version_scope
    ):
        _reject(ChangeReportReadFailure.AUTHORIZATION_DENIED, "authorization")


def _validation_fingerprint(document: Mapping[str, object]) -> str:
    formal = _mapping(document.get("formal_validation"), "validation_report.formal_validation")
    return contract_fingerprint(formal)


def _validate_lineage(
    query: ChangeReportQuery,
    *,
    stored: StoredAppliedResultPort,
    schedule: Mapping[str, object],
    report: Mapping[str, object],
) -> None:
    try:
        if require_p4_document(report) != "change-report.v1":
            _reject(ChangeReportReadFailure.CONTRACT_REJECTED, "change_report_version")
        if require_p4_document(schedule) != "schedule-version.v2":
            _reject(ChangeReportReadFailure.CONTRACT_REJECTED, "schedule_version_version")
        if require_p4_document(stored.solver_report) != "solver-report.v2":
            _reject(ChangeReportReadFailure.CONTRACT_REJECTED, "solver_report_version")
    except ChangeReportReadError:
        raise
    except (TypeError, ValueError) as error:
        raise ChangeReportReadError(
            ChangeReportReadFailure.CONTRACT_REJECTED,
            field=cast(str, getattr(error, "field", "document")),
        ) from error

    result = stored.result
    if (
        result.get("planning_run_terminal_state") != "COMPLETED"
        or result.get("result_fingerprint") != query.expected_result_fingerprint
    ):
        _reject(ChangeReportReadFailure.LINEAGE_MISMATCH, "result")
    report_reference = _mapping(result.get("change_report"), "result.change_report")
    schedule_reference = _mapping(
        result.get("new_schedule_version"), "result.new_schedule_version"
    )
    if (
        report.get("report_id") != query.expected_report_id
        or report.get("report_fingerprint") != query.expected_report_fingerprint
        or report_reference.get("artifact_id") != report.get("report_id")
        or report_reference.get("fingerprint") != report.get("report_fingerprint")
        or schedule.get("schedule_version_id") != query.expected_schedule_version_id
        or schedule.get("content_fingerprint")
        != query.expected_schedule_content_fingerprint
        or schedule_reference.get("artifact_id") != schedule.get("schedule_version_id")
        or schedule_reference.get("fingerprint") != schedule.get("content_fingerprint")
    ):
        _reject(ChangeReportReadFailure.LINEAGE_MISMATCH, "result/report/schedule")

    report_new = _mapping(report.get("new_schedule_version"), "change_report.new_schedule_version")
    report_lineage = _mapping(report.get("lineage"), "change_report.lineage")
    schedule_lineage = _mapping(schedule.get("lineage"), "schedule_version.lineage")
    if (
        report_new.get("schedule_version_id") != schedule.get("schedule_version_id")
        or report_new.get("content_fingerprint") != schedule.get("content_fingerprint")
        or schedule_lineage.get("change_report")
        != {
            "change_report_version": "change-report.v1",
            "report_id": report.get("report_id"),
            "report_fingerprint": report.get("report_fingerprint"),
        }
        or report_lineage.get("replan_request") != schedule_lineage.get("replan_request")
        or report_lineage.get("planning_run_id") != result.get("planning_run_id")
        or report_lineage.get("planning_run_id") != schedule_lineage.get("planning_run_id")
    ):
        _reject(ChangeReportReadFailure.LINEAGE_MISMATCH, "change_report/schedule.lineage")

    solver_id, solver_fingerprint = _reference(
        report_lineage.get("solver_report"), "change_report.lineage.solver_report"
    )
    validation_id, validation_fingerprint = _reference(
        report_lineage.get("validation_report"),
        "change_report.lineage.validation_report",
    )
    after_kpi_id, after_kpi_fingerprint = _reference(
        report.get("after_kpi"), "change_report.after_kpi"
    )
    result_solver = _mapping(result.get("solver_report"), "result.solver_report")
    result_validation = _mapping(
        result.get("validation_report"), "result.validation_report"
    )
    expected_validation_fingerprint = _validation_fingerprint(
        stored.validation_report
    )
    if (
        report_lineage.get("solver_report") != result_solver
        or schedule_lineage.get("solver_report") != result_solver
        or solver_id != stored.solver_report.get("report_id")
        or solver_fingerprint != stored.solver_report.get("report_fingerprint")
        or report_lineage.get("validation_report") != result_validation
        or schedule_lineage.get("validation_report") != result_validation
        or validation_id
        != "validation-report-"
        + expected_validation_fingerprint.removeprefix("sha256:")
        or validation_fingerprint != expected_validation_fingerprint
        or after_kpi_id != stored.kpi.get("kpi_id")
        or after_kpi_fingerprint != contract_fingerprint(stored.kpi)
        or schedule_lineage.get("kpi") != report.get("after_kpi")
        or report.get("correlation_id") != result.get("correlation_id")
    ):
        _reject(ChangeReportReadFailure.LINEAGE_MISMATCH, "artifact_lineage")


class ChangeReportQueryService:
    """Read one immutable applied result without Solver calls or state writes."""

    def __init__(
        self,
        *,
        lineage_repository: ChangeReportLineageRepositoryPort,
        schedule_repository: ChangeReportScheduleRepositoryPort,
    ) -> None:
        self._lineage = lineage_repository
        self._schedules = schedule_repository

    @property
    def solver_invocations(self) -> int:
        return 0

    def query(
        self,
        query: ChangeReportQuery,
        context: ChangeReportReadContext,
        *,
        generated_at_utc: str,
    ) -> ChangeReportReadResult:
        _validate_query(query)
        _authorize(query, context)
        try:
            parsed = parse_utc_instant(generated_at_utc)
        except (TypeError, ValueError) as error:
            raise ChangeReportReadError(
                ChangeReportReadFailure.INVALID_QUERY, field="generated_at_utc"
            ) from error
        if parsed.utcoffset() is None or not generated_at_utc.endswith("Z"):
            _reject(ChangeReportReadFailure.INVALID_QUERY, "generated_at_utc")
        try:
            stored = self._lineage.get_applied_result_for_attempt(query.attempt_id)
        except ChangeReportReadError:
            raise
        except Exception as error:
            raise ChangeReportReadError(
                ChangeReportReadFailure.PERSISTENCE_FAILED,
                field="lineage_repository",
            ) from error
        if stored is None:
            _reject(ChangeReportReadFailure.SOURCE_NOT_FOUND, "attempt_id")
        try:
            schedule = self._schedules.get(query.expected_schedule_version_id)
        except ChangeReportReadError:
            raise
        except Exception as error:
            raise ChangeReportReadError(
                ChangeReportReadFailure.PERSISTENCE_FAILED,
                field="schedule_repository",
            ) from error
        if schedule is None:
            _reject(ChangeReportReadFailure.SOURCE_NOT_FOUND, "schedule_version_id")

        report = deepcopy(stored.change_report)
        detached_schedule = deepcopy(schedule)
        _validate_lineage(
            query,
            stored=stored,
            schedule=detached_schedule,
            report=report,
        )
        raw_operations = report.get("operations")
        if not isinstance(raw_operations, list):
            _reject(ChangeReportReadFailure.CONTRACT_REJECTED, "operations")
        operations = [
            deepcopy(cast(dict[str, object], operation))
            for operation in raw_operations
            if isinstance(operation, Mapping)
            and (not query.classifications or operation.get("classification") in query.classifications)
            and (not query.operation_ids or operation.get("operation_id") in query.operation_ids)
            and (
                query.after_operation_id is None
                or cast(str, operation.get("operation_id", "")) > query.after_operation_id
            )
        ]
        operations.sort(key=lambda item: cast(str, item["operation_id"]))
        page = operations[: query.limit]
        next_cursor = (
            cast(str, page[-1]["operation_id"])
            if len(operations) > query.limit and page
            else None
        )
        state = detached_schedule.get("state")
        export_eligible = (
            state == "PUBLISHED"
            and "export" in cast(Sequence[object], detached_schedule.get("allowed_actions", ()))
            and detached_schedule.get("publication") is not None
        )
        document: dict[str, object] = {
            "read_model_version": CHANGE_REPORT_READ_MODEL_VERSION,
            "canonicalization_version": "canonical-json.v1",
            "data_plane": "SIMULATION",
            "environment": context.environment,
            "query": {
                "attempt_id": query.attempt_id,
                "expected_result_fingerprint": query.expected_result_fingerprint,
                "expected_schedule_version_id": query.expected_schedule_version_id,
                "expected_schedule_content_fingerprint": query.expected_schedule_content_fingerprint,
                "expected_report_id": query.expected_report_id,
                "expected_report_fingerprint": query.expected_report_fingerprint,
                "classifications": list(query.classifications),
                "operation_ids": list(query.operation_ids),
                "after_operation_id": query.after_operation_id,
                "limit": query.limit,
            },
            "result": {
                "replan_result": {
                    "result_id": stored.result["result_id"],
                    "result_fingerprint": stored.result["result_fingerprint"],
                    "attempt_id": stored.result["attempt_id"],
                    "request_id": stored.result["request_id"],
                    "request_fingerprint": stored.result["request_fingerprint"],
                    "planning_run_id": stored.result["planning_run_id"],
                },
                "schedule_version": {
                    "schedule_version_version": "schedule-version.v2",
                    "schedule_version_id": detached_schedule["schedule_version_id"],
                    "state": state,
                    "content_fingerprint": detached_schedule["content_fingerprint"],
                },
                "change_report": {
                    "change_report_version": "change-report.v1",
                    "report_id": report["report_id"],
                    "report_fingerprint": report["report_fingerprint"],
                },
                "lineage": deepcopy(report["lineage"]),
                "before_kpi": deepcopy(report["before_kpi"]),
                "after_kpi": deepcopy(report["after_kpi"]),
                "stability": deepcopy(report["stability"]),
                "operation_universe_count": report["operation_universe_count"],
                "filtered_operation_count": len(operations),
                "operations": page,
                "next_cursor": next_cursor,
                "export_eligible": export_eligible,
                "publishable": False,
            },
            "generated_at_utc": generated_at_utc,
            "boundary": {
                "side_effects": "NONE",
                "schedule_state_changed": False,
                "replan_state_changed": False,
                "production": "NOT_AUTHORIZED",
                "external_transfer": "NOT_STARTED",
            },
        }
        document["read_fingerprint"] = contract_fingerprint(document)
        detached = cast(
            dict[str, object],
            json.loads(canonical_contract_bytes(document)),
        )
        return ChangeReportReadResult(
            document=detached,
            change_report=report,
            schedule_version=detached_schedule,
        )


__all__ = [
    "CHANGE_REPORT_READ_MODEL_VERSION",
    "ChangeReportQuery",
    "ChangeReportQueryService",
    "ChangeReportReadContext",
    "ChangeReportReadError",
    "ChangeReportReadFailure",
    "ChangeReportReadResult",
]
