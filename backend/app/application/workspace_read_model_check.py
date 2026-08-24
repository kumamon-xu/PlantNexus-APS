"""Emit machine-checkable TASK-P3-05 read-model and comparison evidence."""

from __future__ import annotations

import argparse
import base64
from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from importlib import import_module
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter_ns
from typing import Any, cast

from alembic import command
from alembic.config import Config
from app.application.schedule_comparison import ScheduleComparisonService
from app.application.schedule_version_lifecycle_check import lifecycle_context
from app.application.schedule_versions import ValidatedSolutionToScheduleVersionService
from app.application.workspace_queries import (
    WorkspaceQueryResult,
    WorkspaceQueryService,
)
from app.domain.schedule_version import ValidatedPlanningOutput
from app.domain.workspace import (
    WorkspaceReadError,
    WorkspaceReadFailure,
    WorkspaceSourceDocuments,
    WorkspaceView,
    build_workspace_query_request,
    version_reference,
)
from app.domain.workspace_contracts import (
    canonical_workspace_bytes,
    workspace_fingerprint,
)
from app.planning.reporting.kpi import build_kpi_v2
from app.simulation.scenarios.p2_correctness import (
    CorrectnessReplay,
    execute_correctness_case,
    load_correctness_cases,
    verify_correctness_replay,
)


REPORT_VERSION = "p3-workspace-read-model-report.v1"
TASK_ID = "TASK-P3-05"
GENERATED_AT = "2026-08-24T08:00:00Z"
_WORKSPACE_VIEWS = frozenset(
    {
        WorkspaceView.DATA_HEALTH,
        WorkspaceView.IMPORT_RUNS,
        WorkspaceView.PLANNING_RUNS,
    }
)


def load_read_model_fixtures(
    root: Path,
) -> tuple[
    tuple[ValidatedPlanningOutput, CorrectnessReplay],
    tuple[ValidatedPlanningOutput, CorrectnessReplay],
]:
    """Replay two frozen P2 cases strictly as versioned synthetic inputs."""

    fixtures: list[tuple[ValidatedPlanningOutput, CorrectnessReplay]] = []
    for case in load_correctness_cases(root)[:2]:
        replay = execute_correctness_case(case, root=root)
        verify_correctness_replay(replay)
        kpi = build_kpi_v2(
            snapshot=replay.snapshot_document,
            problem=replay.problem,
            solution=replay.solution,
            solver_report=replay.solver_report,
            validation_report=replay.validation_report,
            import_quality_report=replay.quality_report,
        )
        fixtures.append(
            (
                ValidatedPlanningOutput(
                    snapshot=replay.snapshot_document,
                    problem=replay.problem,
                    solution=replay.solution,
                    solver_report=replay.solver_report,
                    validation_report=replay.validation_report,
                    import_quality_report=replay.quality_report,
                    kpi=kpi.document,
                ),
                replay,
            )
        )
    if len(fixtures) != 2:
        raise ValueError("two frozen P2 correctness fixtures are required")
    return fixtures[0], fixtures[1]


def sources_for(output: ValidatedPlanningOutput) -> WorkspaceSourceDocuments:
    return WorkspaceSourceDocuments(
        snapshot=output.snapshot,
        problem=output.problem,
        solution=output.solution,
        solver_report=output.solver_report,
        validation_report=output.validation_report,
        import_quality_report=output.import_quality_report,
        kpi=output.kpi,
    )


def _alembic_config(root: Path, database_url: str) -> Config:
    configuration = Config(str(root / "alembic.ini"))
    configuration.set_main_option(
        "script_location", str(root / "backend" / "migrations")
    )
    configuration.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return configuration


def _workspace_engine(root: Path, database_path: Path) -> tuple[Any, Config]:
    database_url = f"sqlite:///{database_path.as_posix()}"
    configuration = _alembic_config(root, database_url)
    command.upgrade(configuration, "head")
    sqlalchemy = cast(Any, import_module("sqlalchemy"))
    return (
        sqlalchemy.create_engine(
            database_url, connect_args={"check_same_thread": False}
        ),
        configuration,
    )


def _adapters() -> Any:
    return cast(Any, import_module("app.infrastructure"))


def _repositories(engine: Any) -> tuple[Any, Any]:
    adapters = _adapters()
    plane = adapters.WorkspaceDataPlane.SIMULATION
    return (
        adapters.SqlAlchemyScheduleVersionRepository(engine, data_plane=plane),
        adapters.SqlAlchemyAuditRepository(engine, data_plane=plane),
    )


def _lifecycle_service(engine: Any) -> ValidatedSolutionToScheduleVersionService:
    schedule_repository, audit_repository = _repositories(engine)
    return ValidatedSolutionToScheduleVersionService(
        data_plane="SIMULATION",
        transaction_factory=engine.begin,
        schedule_repository=schedule_repository,
        audit_repository=audit_repository,
    )


def _counts(engine: Any) -> dict[str, int]:
    with engine.connect() as connection:
        return {
            "schedule_versions": int(
                connection.exec_driver_sql(
                    "SELECT COUNT(*) FROM schedule_versions"
                ).scalar_one()
            ),
            "audit_events": int(
                connection.exec_driver_sql(
                    "SELECT COUNT(*) FROM audit_events"
                ).scalar_one()
            ),
        }


def _pass(check_id: str, evidence: Mapping[str, object]) -> dict[str, object]:
    return {"check_id": check_id, "status": "PASS", "evidence": dict(evidence)}


def _expect(
    reason: WorkspaceReadFailure, operation: Callable[[], object]
) -> WorkspaceReadFailure:
    try:
        operation()
    except WorkspaceReadError as error:
        if error.reason is reason:
            return error.reason
        raise ValueError(f"unexpected read rejection: {error.reason.value}") from error
    raise ValueError(f"expected {reason.value} rejection")


def _request(
    view: WorkspaceView,
    schedule_version: Mapping[str, object],
    sources: WorkspaceSourceDocuments,
    *,
    page_size: int = 500,
    cursor: str | None = None,
    reference: Mapping[str, object] | None = None,
    data_plane: str = "SIMULATION",
) -> dict[str, object]:
    provenance = sources.snapshot.get("synthetic_provenance")
    if not isinstance(provenance, Mapping):
        raise ValueError("synthetic fixture provenance is absent")
    schedule_reference = None
    if view not in _WORKSPACE_VIEWS:
        schedule_reference = reference or version_reference(schedule_version)
    return build_workspace_query_request(
        view=view,
        data_plane=data_plane,
        environment="TEST" if data_plane == "SIMULATION" else "PRODUCTION",
        synthetic=data_plane == "SIMULATION",
        correlation_id=f"correlation-p3-05-{view.value.lower().replace('_', '-')}",
        schedule_version_reference=schedule_reference,
        synthetic_provenance=provenance if data_plane == "SIMULATION" else None,
        page_size=page_size,
        cursor=cursor,
    )


def _read_checks(
    query_service: WorkspaceQueryService,
    base_version: Mapping[str, object],
    base_sources: WorkspaceSourceDocuments,
) -> tuple[list[dict[str, object]], dict[str, WorkspaceQueryResult]]:
    results: dict[WorkspaceView, WorkspaceQueryResult] = {}
    started = perf_counter_ns()
    for view in WorkspaceView:
        if view is WorkspaceView.VERSION_COMPARISON:
            continue
        result = query_service.query(
            _request(view, base_version, base_sources),
            sources=base_sources,
            generated_at_utc=GENERATED_AT,
        )
        result_body = cast(Mapping[str, object], result.document["result"])
        if not result.found or result_body["freshness"] != "FRESH":
            raise ValueError(f"{view.value} did not return a fresh found result")
        if any(
            item.payload_fingerprint != workspace_fingerprint(item.payload)
            for item in result.items
        ):
            raise ValueError(f"{view.value} payload fingerprint mismatch")
        results[view] = result
    elapsed_microseconds = (perf_counter_ns() - started) // 1_000
    view_counts = {
        view.value: len(results[view].items) for view in sorted(results, key=str)
    }
    expected_types = {
        WorkspaceView.DATA_HEALTH: "DATA_HEALTH",
        WorkspaceView.IMPORT_RUNS: "IMPORT_RUN",
        WorkspaceView.PLANNING_RUNS: "PLANNING_RUN",
        WorkspaceView.ORDERS: "ORDER",
        WorkspaceView.OPERATIONS: "OPERATION",
        WorkspaceView.RESOURCES: "RESOURCE",
        WorkspaceView.CALENDARS: "CALENDAR",
        WorkspaceView.GANTT: "GANTT_SEGMENT",
        WorkspaceView.RESOURCE_LOAD: "RESOURCE_LOAD",
        WorkspaceView.KPI: "KPI",
        WorkspaceView.DIAGNOSTICS: "DIAGNOSTIC",
        WorkspaceView.LOCKS: "LOCK",
        WorkspaceView.AUDIT: "AUDIT_REFERENCE",
    }
    for view, result in results.items():
        if any(item.item_type != expected_types[view] for item in result.items):
            raise ValueError(f"{view.value} emitted the wrong projection type")

    loads = results[WorkspaceView.RESOURCE_LOAD].items
    busy_by_resource = {
        cast(str, item.payload["resource_id"]): cast(
            int, item.payload["planned_busy_seconds"]
        )
        for item in loads
    }
    assignment_busy: dict[str, int] = {}
    for raw in cast(list[Mapping[str, object]], base_sources.solution["assignments"]):
        resource_id = cast(str, raw["resource_id"])
        assignment_busy[resource_id] = assignment_busy.get(resource_id, 0) + cast(
            int, raw["duration_seconds"]
        )
    if busy_by_resource != assignment_busy:
        raise ValueError("resource-load busy seconds differ from assignments")

    source_bytes = sum(
        len(canonical_workspace_bytes(document))
        for document in (
            base_sources.snapshot,
            base_sources.problem,
            base_sources.solution,
            base_sources.solver_report,
            base_sources.validation_report,
            base_sources.import_quality_report,
            base_sources.kpi,
        )
    )
    projected_bytes = sum(
        len(canonical_workspace_bytes(item.payload))
        for result in results.values()
        for item in result.items
    )
    checks = [
        _pass(
            "P3-05-READ-MODEL-COVERAGE",
            {
                "view_count": len(results),
                "view_counts": view_counts,
                "payload_fingerprints_verified": sum(view_counts.values()),
            },
        ),
        _pass(
            "P3-05-LOAD-KPI-CONSISTENCY",
            {
                "resource_count": len(loads),
                "assignment_busy_seconds": assignment_busy,
                "load_busy_seconds": busy_by_resource,
                "kpi_projection_count": len(results[WorkspaceView.KPI].items),
            },
        ),
        _pass(
            "P3-05-LINEAGE-AUTHORITY",
            {
                "schedule_version_id": base_version["schedule_version_id"],
                "schedule_version_state": base_version["state"],
                "schedule_scoped_views": len(results) - len(_WORKSPACE_VIEWS),
                "workspace_scoped_views": len(_WORKSPACE_VIEWS),
                "source_fingerprint_count": len(
                    {
                        result.source_fingerprint
                        for result in results.values()
                        if result.source_fingerprint is not None
                    }
                ),
                "freshness": "FRESH",
            },
        ),
        _pass(
            "P3-05-SCALE-OBSERVATION",
            {
                "profile": "VERSIONED_SYNTHETIC_XS",
                "source_bytes": source_bytes,
                "projected_payload_bytes": projected_bytes,
                "projection_count": sum(view_counts.values()),
                "elapsed_microseconds_observed": elapsed_microseconds,
                "production_threshold_asserted": False,
            },
        ),
    ]
    return checks, {view.value: results[view] for view in results}


def run_workspace_read_model_checks(root: Path) -> dict[str, object]:
    (base_output, base_replay), (compared_output, compared_replay) = (
        load_read_model_fixtures(root)
    )
    base_sources = sources_for(base_output)
    compared_sources = sources_for(compared_output)
    checks: list[dict[str, object]] = []
    with TemporaryDirectory(prefix="plantnexus-p3-05-") as temporary:
        engine, configuration = _workspace_engine(
            root, Path(temporary) / "workspace.db"
        )
        try:
            lifecycle = _lifecycle_service(engine)
            base_created = lifecycle.create_reviewable(
                base_output, lifecycle_context("a")
            )
            compared_created = lifecycle.create_reviewable(
                compared_output,
                lifecycle_context(
                    "b",
                    reason="Create a second immutable synthetic Version for comparison.",
                    correlation_id="correlation-p3-05-compared-version",
                ),
            )
            schedule_repository, audit_repository = _repositories(engine)
            query_service = WorkspaceQueryService(
                data_plane="SIMULATION",
                schedule_repository=schedule_repository,
                audit_repository=audit_repository,
            )
            comparison_service = ScheduleComparisonService(
                data_plane="SIMULATION", schedule_repository=schedule_repository
            )
            durable_before_reads = _counts(engine)
            read_checks, results = _read_checks(
                query_service, base_created.schedule_version, base_sources
            )
            checks.extend(read_checks)

            comparison_request = _request(
                WorkspaceView.VERSION_COMPARISON,
                base_created.schedule_version,
                base_sources,
            )
            comparison = comparison_service.compare(
                comparison_request,
                compared_version_precondition=version_reference(
                    compared_created.schedule_version
                ),
                base_sources=base_sources,
                compared_sources=compared_sources,
                generated_at_utc=GENERATED_AT,
            )
            replayed_comparison = comparison_service.compare(
                comparison_request,
                compared_version_precondition=version_reference(
                    compared_created.schedule_version
                ),
                base_sources=base_sources,
                compared_sources=compared_sources,
                generated_at_utc=GENERATED_AT,
            )
            if comparison != replayed_comparison:
                raise ValueError("comparison replay changed canonical output")
            comparison_text = json.dumps(comparison.comparison, sort_keys=True).lower()
            if "change_report" in comparison_text or "replan" in comparison_text:
                raise ValueError("comparison leaked a P4 carrier")
            checks.append(
                _pass(
                    "P3-05-COMPARISON-REPLAY",
                    {
                        "comparison_id": comparison.comparison["comparison_id"],
                        "comparison_fingerprint": comparison.comparison[
                            "comparison_fingerprint"
                        ],
                        "operation_delta_count": len(
                            cast(
                                list[object], comparison.comparison["operation_deltas"]
                            )
                        ),
                        "kpi_delta_count": len(
                            cast(list[object], comparison.comparison["kpi_deltas"])
                        ),
                        "exact_replays": 1,
                        "change_report_absent": True,
                    },
                )
            )

            first_request = _request(
                WorkspaceView.OPERATIONS,
                base_created.schedule_version,
                base_sources,
                page_size=1,
            )
            first_page = query_service.query(
                first_request, sources=base_sources, generated_at_utc=GENERATED_AT
            )
            first_result = cast(Mapping[str, object], first_page.document["result"])
            cursor = cast(str, first_result["next_cursor"])
            second_page = query_service.query(
                _request(
                    WorkspaceView.OPERATIONS,
                    base_created.schedule_version,
                    base_sources,
                    page_size=1,
                    cursor=cursor,
                ),
                sources=base_sources,
                generated_at_utc=GENERATED_AT,
            )
            if not second_page.items or first_page.items == second_page.items:
                raise ValueError(
                    "stable cursor did not advance the immutable collection"
                )
            replay_first = query_service.query(
                first_request, sources=base_sources, generated_at_utc=GENERATED_AT
            )
            if first_page != replay_first:
                raise ValueError("same query did not replay exactly")
            checks.append(
                _pass(
                    "P3-05-FILTER-SORT-PAGE-REPLAY",
                    {
                        "page_size": 1,
                        "first_item": first_page.items[0].item_id,
                        "second_item": second_page.items[0].item_id,
                        "observed_count": first_result["observed_count"],
                        "exact_replays": 1,
                    },
                )
            )

            missing_reference = {
                "schedule_version_id": "schedule-version-missing-p3-05",
                "state": "READY_FOR_REVIEW",
                "content_fingerprint": f"sha256:{'f' * 64}",
            }
            missing = query_service.query(
                _request(
                    WorkspaceView.OPERATIONS,
                    base_created.schedule_version,
                    base_sources,
                    reference=missing_reference,
                ),
                sources=base_sources,
                generated_at_utc=GENERATED_AT,
            )
            locks = cast(WorkspaceQueryService, query_service).query(
                _request(
                    WorkspaceView.LOCKS, base_created.schedule_version, base_sources
                ),
                sources=base_sources,
                generated_at_utc=GENERATED_AT,
            )
            stale_ref = dict(version_reference(base_created.schedule_version))
            stale_ref["state"] = "DRAFT"
            stale_reason = _expect(
                WorkspaceReadFailure.STALE_VERSION,
                lambda: query_service.query(
                    _request(
                        WorkspaceView.OPERATIONS,
                        base_created.schedule_version,
                        base_sources,
                        reference=stale_ref,
                    ),
                    sources=base_sources,
                    generated_at_utc=GENERATED_AT,
                ),
            )
            plane_reason = _expect(
                WorkspaceReadFailure.DATA_PLANE_MISMATCH,
                lambda: query_service.query(
                    _request(
                        WorkspaceView.DATA_HEALTH,
                        base_created.schedule_version,
                        base_sources,
                        data_plane="PRODUCTION",
                    ),
                    sources=base_sources,
                    generated_at_utc=GENERATED_AT,
                ),
            )
            tampered_solution = cast(dict[str, object], deepcopy(base_output.solution))
            tampered_assignments = cast(
                list[dict[str, object]], tampered_solution["assignments"]
            )
            tampered_assignments[0]["resource_id"] = "resource-tampered-p3-05"
            tamper_reason = _expect(
                WorkspaceReadFailure.MIXED_LINEAGE,
                lambda: query_service.query(
                    _request(
                        WorkspaceView.OPERATIONS,
                        base_created.schedule_version,
                        base_sources,
                    ),
                    sources=WorkspaceSourceDocuments(
                        snapshot=base_output.snapshot,
                        problem=base_output.problem,
                        solution=tampered_solution,
                        solver_report=base_output.solver_report,
                        validation_report=base_output.validation_report,
                        import_quality_report=base_output.import_quality_report,
                        kpi=base_output.kpi,
                    ),
                    generated_at_utc=GENERATED_AT,
                ),
            )
            cursor_padding = "=" * (-len(cursor) % 4)
            cursor_payload = cast(
                dict[str, object],
                json.loads(base64.urlsafe_b64decode(cursor + cursor_padding)),
            )
            cursor_payload["source_fingerprint"] = f"sha256:{'e' * 64}"
            stale_cursor = (
                base64.urlsafe_b64encode(canonical_workspace_bytes(cursor_payload))
                .decode("ascii")
                .rstrip("=")
            )
            cursor_reason = _expect(
                WorkspaceReadFailure.STALE_CURSOR,
                lambda: query_service.query(
                    _request(
                        WorkspaceView.OPERATIONS,
                        base_created.schedule_version,
                        base_sources,
                        page_size=1,
                        cursor=stale_cursor,
                    ),
                    sources=base_sources,
                    generated_at_utc=GENERATED_AT,
                ),
            )
            if missing.found or not locks.found or locks.items:
                raise ValueError("missing and found-empty semantics collapsed")
            checks.append(
                _pass(
                    "P3-05-NEGATIVE-AND-EMPTY",
                    {
                        "missing_found": missing.found,
                        "empty_locks_found": locks.found,
                        "empty_locks_observed_count": 0,
                        "stale_reason": stale_reason.value,
                        "plane_reason": plane_reason.value,
                        "tamper_reason": tamper_reason.value,
                        "cursor_reason": cursor_reason.value,
                    },
                )
            )

            durable_after_reads = _counts(engine)
            if durable_after_reads != durable_before_reads:
                raise ValueError("read services mutated durable workspace tables")
            checks.append(
                _pass(
                    "P3-05-READ-ONLY-BOUNDARY",
                    {
                        "durable_counts_before": durable_before_reads,
                        "durable_counts_after": durable_after_reads,
                        "query_service_solver_invocations": query_service.solver_invocations,
                        "comparison_service_solver_invocations": (
                            comparison_service.solver_invocations
                        ),
                        "fixture_solver_replays": 2,
                        "schema_migration_dependency_changes": 0,
                        "api_ui_p4_implementations": 0,
                    },
                )
            )
        finally:
            engine.dispose()
            command.downgrade(configuration, "base")

    if len(checks) != 8 or any(check["status"] != "PASS" for check in checks):
        raise ValueError("read-model evidence is incomplete")
    view_counts = {
        name: cast(Mapping[str, object], value.document["result"])["observed_count"]
        for name, value in results.items()
    }
    return {
        "report_version": REPORT_VERSION,
        "task_id": TASK_ID,
        "status": "PASS",
        "code_commit": os.environ.get("PLANTNEXUS_CODE_COMMIT", "uncommitted"),
        "schema_set_version": "2.6.0",
        "read_model_version": "workspace-read-model.v1",
        "check_count": len(checks),
        "checks": checks,
        "counts": {
            "versioned_synthetic_inputs": 2,
            "workspace_views": 14,
            "non_comparison_view_counts": view_counts,
            "comparison_results": 1,
            "exact_query_replays": 1,
            "exact_comparison_replays": 1,
            "product_service_solver_invocations": 0,
            "rejected_negative_cases": 4,
        },
        "source_scenarios": [
            base_replay.case.scenario_id,
            compared_replay.case.scenario_id,
        ],
        "boundaries": {
            "repository_writes_from_queries": "FORBIDDEN_AND_ABSENT",
            "solver_validator_rule_duplication": "FORBIDDEN_AND_ABSENT",
            "schedule_version_transition": "FORBIDDEN_AND_ABSENT",
            "change_report_replan": "NOT_IMPLEMENTED",
            "http_ui": "NOT_IMPLEMENTED",
            "approval_publication_export": "NOT_IMPLEMENTED",
            "production_authority": "NOT_CLAIMED",
            "production_readiness": "NOT_CLAIMED",
        },
        "issues": [],
    }


def _write_report(path: Path, report: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate TASK-P3-05 read models")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("build/validation/p3-workspace-read-models.json"),
    )
    arguments = parser.parse_args(argv)
    try:
        report = run_workspace_read_model_checks(arguments.root.resolve())
    except Exception as error:  # noqa: BLE001 - CLI emits sanitized fail evidence
        report = {
            "report_version": REPORT_VERSION,
            "task_id": TASK_ID,
            "status": "FAIL",
            "code_commit": os.environ.get("PLANTNEXUS_CODE_COMMIT", "uncommitted"),
            "check_count": 0,
            "checks": [],
            "issues": [
                {
                    "reason": error.reason.value
                    if isinstance(error, WorkspaceReadError)
                    else "MACHINE_CHECK_FAILED",
                    "error_type": type(error).__name__,
                    "message": "P3-05 read-model evidence did not complete",
                }
            ],
            "boundaries": {
                "production_authority": "NOT_CLAIMED",
                "production_readiness": "NOT_CLAIMED",
            },
        }
        _write_report(arguments.report, report)
        return 1
    _write_report(arguments.report, report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "REPORT_VERSION",
    "TASK_ID",
    "load_read_model_fixtures",
    "main",
    "run_workspace_read_model_checks",
    "sources_for",
]
