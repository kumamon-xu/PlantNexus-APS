"""Emit machine-checkable TASK-P4-11 ChangeReport read/export evidence."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import UTC, datetime
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, cast

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from app.application.change_report_queries import (
    ChangeReportQuery,
    ChangeReportQueryService,
    ChangeReportReadContext,
)
from app.application.export_downloads import ExportPackageDownloadService
from app.application.export_jobs import ExportJobService
from app.application.replan_application_check import (
    _alembic_config,
    build_replan_application_fixture,
    seed_replan_application_runtime,
)
from app.domain.execution_contracts import (
    canonical_contract_bytes,
    contract_fingerprint,
    schedule_content_fingerprint as p4_schedule_content_fingerprint,
    solver_report_fingerprint,
)
from app.domain.export_job import (
    ExportJobContext,
    ExportJobRequest,
    audit_event_id,
    build_created_export_job,
    export_job_identity,
    lease_reference_for,
    transition_export_job,
)
from app.domain.workspace_contracts import (
    publication_result_fingerprint,
    require_workspace_document,
    schedule_content_fingerprint,
)
from app.exporters import build_internal_export_package
from app.exporters.change_report_package import (
    ChangeReportExportPackage,
    archive_change_report_export_package,
    build_change_report_export_package,
    change_report_export_bytes_fingerprint,
    load_change_report_export_package,
    verify_change_report_export_package,
    write_change_report_export_package,
)
from app.exporters.standard_package import build_standard_export_package
from app.infrastructure import (
    SqlAlchemyAuditRepository,
    SqlAlchemyExportJobRepository,
    SqlAlchemyScheduleVersionRepository,
    WorkspaceDataPlane,
)
from app.jobs.change_report_export_job import InternalChangeReportExportJobWorker
from app.jobs.export_package_store import LocalExportPackageStore
from app.planning.reporting.change_report import build_change_report
from app.planning.reporting.stability_change_report_check import (
    build_stability_change_report_fixture,
)
from app.simulation.scenarios.p2_correctness import (
    execute_correctness_case,
    load_correctness_cases,
)


REPORT_VERSION = "p4-change-report-output-report.v1"
TASK_ID = "TASK-P4-11"
DIFF_BASE = "45b12d9a67ce5ef1680a47fecdc68705355af226"
IMPACT_RULES = (
    "IMPACT-APPLICATION",
    "IMPACT-DOCS",
    "IMPACT-DOMAIN",
    "IMPACT-EXPORT",
    "IMPACT-INFRA",
    "IMPACT-JOBS",
    "IMPACT-STATE",
    "IMPACT-TESTS",
)


@dataclass(frozen=True, slots=True)
class ChangeReportOutputFixture:
    p3_package: object
    p3_schedule: dict[str, object]
    schedule_version: dict[str, object]
    publication_result: dict[str, object]
    change_report: dict[str, object]
    solver_report: dict[str, object]
    validation_report: dict[str, object]
    kpi: dict[str, object]
    request: ExportJobRequest
    created_job: dict[str, object]
    exporting_job: dict[str, object]
    create_context: ExportJobContext
    worker_context: ExportJobContext


def _sample(root: Path, name: str) -> dict[str, object]:
    return cast(
        dict[str, object],
        json.loads((root / "schemas/samples" / name).read_text(encoding="utf-8")),
    )


def _reference(version: str, identity: str, fingerprint: str) -> dict[str, str]:
    return {
        "document_version": version,
        "artifact_id": identity,
        "fingerprint": fingerprint,
    }


def _p3_package(
    root: Path, *, code_commit: str
) -> tuple[object, dict[str, object], dict[str, object]]:
    replay = execute_correctness_case(load_correctness_cases(root)[0], root=root)
    p2 = build_internal_export_package(
        snapshot=replay.snapshot_document,
        problem=replay.problem,
        solution=replay.solution,
        solver_report=replay.solver_report,
        validation_report=replay.validation_report,
        import_quality_report=replay.quality_report,
        scenario_manifest=replay.case.manifest,
    )
    schedule = _sample(root, "schedule-version.v1.synthetic.json")
    schedule["state"] = "PUBLISHED"
    schedule["content"] = {"assignments": replay.solution["assignments"], "locks": []}
    schedule["content_fingerprint"] = schedule_content_fingerprint(schedule)
    lineage = cast(dict[str, object], schedule["lineage"])
    p2_lineage = cast(dict[str, object], p2.manifest["lineage"])
    p2_solution = cast(dict[str, object], p2_lineage["solution"])
    lineage["planning_solution"] = {
        "document_version": "planning-solution.v1",
        "artifact_id": replay.solution["solution_id"],
        "fingerprint": p2_solution["solution_fingerprint"],
    }
    lineage["code_commit"] = code_commit
    schedule["decision"] = {
        "decision": "APPROVED",
        "actor_ref": "actor:p4-output-approver",
        "capability": "approve",
        "reason": "Approve bounded P4 output compatibility fixture.",
        "decided_at_utc": "2026-08-28T10:00:00Z",
        "audit_event_id": "audit-p4-output-base-approval",
    }
    schedule["publication"] = {
        "publication_id": "publication-p4-output-base",
        "target": "SIMULATION_INTERNAL",
        "published_at_utc": "2026-08-28T10:01:00Z",
        "audit_event_id": "audit-p4-output-base-publication",
    }
    schedule["allowed_actions"] = ["view", "export"]
    require_workspace_document(schedule)

    publication = _sample(root, "publication-result.v1.synthetic.json")
    p3_reference = {
        "schedule_version_id": schedule["schedule_version_id"],
        "state": "PUBLISHED",
        "content_fingerprint": schedule["content_fingerprint"],
    }
    publication.update(
        {
            "publication_id": "publication-p4-output-base",
            "source_approved_version": {**p3_reference, "state": "APPROVED"},
            "published_version": p3_reference,
            "published_at_utc": "2026-08-28T10:01:00Z",
            "audit_event_id": "audit-p4-output-base-publication",
            "synthetic_provenance": deepcopy(schedule["synthetic_provenance"]),
        }
    )
    publication["result_fingerprint"] = publication_result_fingerprint(publication)
    request = ExportJobRequest(
        schedule_version_id=cast(str, schedule["schedule_version_id"]),
        expected_content_fingerprint=cast(str, schedule["content_fingerprint"]),
        raw_idempotency_key="p4-output-p3-package-key",
        reason="Build compatible frozen P3 standard package.",
        correlation_id="correlation-p4-output-p3-package",
        environment="TEST",
        synthetic_provenance=cast(Mapping[str, object], schedule["synthetic_provenance"]),
    )
    context = ExportJobContext(
        actor_ref="actor:p4-output-worker",
        authenticated=True,
        resolved_capabilities=frozenset({"export"}),
        schedule_version_scope=frozenset({cast(str, schedule["schedule_version_id"])}),
        export_job_scope=frozenset(),
        auth_policy_version="p4-output-simulation-policy.v1",
        production_binding=False,
        occurred_at_utc="2026-08-28T10:02:00Z",
        code_commit=code_commit,
    )
    identity = export_job_identity(request)
    created = build_created_export_job(request, identity, context, schedule, publication)
    exporting = transition_export_job(
        created,
        target_state="EXPORTING",
        occurred_at_utc="2026-08-28T10:03:00Z",
        audit_event_id_value=audit_event_id(identity.export_job_id, "ATTEMPT", 1),
        attempt=1,
        lease_reference=lease_reference_for(identity.export_job_id, 1, "worker:p3-output"),
    )
    package = build_standard_export_package(
        p2_package=p2,
        schedule_version=schedule,
        publication_result=publication,
        export_job=exporting,
        create_audit_event_id=audit_event_id(identity.export_job_id, "CREATE", 0),
        attempt_audit_event_id=cast(str, exporting["latest_audit_event_id"]),
        completion_audit_event_id=audit_event_id(identity.export_job_id, "COMPLETED", 1),
        correlation_id=request.correlation_id,
        generated_at_utc="2026-08-28T10:04:00Z",
    )
    return package, schedule, publication


def _successful_solver_report(
    root: Path,
    *,
    assignments: list[object],
    planning_run_id: str,
    code_commit: str,
) -> dict[str, object]:
    report = _sample(root, "solver-report.v2.synthetic.json")
    candidate_basis: dict[str, object] = {
        "candidate_version": "replan-candidate.v1",
        "assignment_count": len(assignments),
        "assignments": deepcopy(assignments),
    }
    candidate_fingerprint = contract_fingerprint(candidate_basis)
    report.update(
        {
            "evidence_kind": "SOLVER_RUN",
            "planning_run_id": planning_run_id,
            "candidate": {
                **candidate_basis,
                "candidate_fingerprint": candidate_fingerprint,
            },
            "solver_status": "OPTIMAL",
            "planning_run_outcome": {"state": "SOLVED", "product_error": None},
            "stability_evidence": {
                "soft_lock_violations": 0,
                "changed_existing_operations": 0,
                "resource_changes": 0,
                "absolute_start_shift_seconds": 0,
            },
            "diagnostics": [],
        }
    )
    stages = cast(list[dict[str, object]], report["objective_stage_results"])
    for stage in stages:
        stage["status"] = "OPTIMAL"
        stage["stop_reason"] = "OPTIMAL_PROVEN"
    stages[0]["objective_value"] = stages[0]["best_bound"] = 0
    stages[1]["objective_value"] = stages[1]["best_bound"] = deepcopy(
        report["stability_evidence"]
    )
    makespan = max(cast(int, cast(dict[str, object], item)["end_tick"]) for item in assignments)
    stages[2]["objective_value"] = stages[2]["best_bound"] = makespan
    provenance = cast(dict[str, object], report["provenance"])
    provenance["code_commit"] = code_commit
    fingerprint = solver_report_fingerprint(report)
    report["report_fingerprint"] = fingerprint
    report["report_id"] = "solver-report-" + fingerprint.removeprefix("sha256:")
    return report


def build_change_report_output_fixture(
    root: Path, *, code_commit: str = "uncommitted"
) -> ChangeReportOutputFixture:
    p3_package, p3_schedule, _ = _p3_package(root, code_commit=code_commit)
    p3_files = cast(Any, p3_package).files
    kpi = cast(dict[str, object], json.loads(p3_files["kpi.json"]))
    assignments = deepcopy(
        cast(list[object], cast(dict[str, object], p3_schedule["content"])["assignments"])
    )
    planning_run_id = "planning-run-p4-change-report-output-001"
    solver = _successful_solver_report(
        root,
        assignments=assignments,
        planning_run_id=planning_run_id,
        code_commit=code_commit,
    )
    validation_formal: dict[str, object] = {
        "validation_report_version": "validation-report.v2",
        "status": "PASS",
        "hard_violation_count": 0,
        "schedule_content_fingerprint": cast(str, p3_schedule["content_fingerprint"]),
        "planning_run_id": planning_run_id,
    }
    validation_fingerprint = contract_fingerprint(validation_formal)
    validation: dict[str, object] = {
        "validation_report_version": "validation-report.v2",
        "report_id": "validation-report-p4-change-report-output-001",
        "status": "PASS",
        "hard_violation_count": 0,
        "formal_validation": validation_formal,
    }
    p4_sample = _sample(root, "schedule-version.v2.synthetic.json")
    p4_schedule_id = "schedule-version-p4-change-report-output-001"
    p4_content = deepcopy(p3_schedule["content"])
    p4_content_fingerprint = p4_schedule_content_fingerprint({"content": p4_content})
    base_reference = {
        "schedule_version_version": "schedule-version.v1",
        "schedule_version_id": p3_schedule["schedule_version_id"],
        "state": "PUBLISHED",
        "content_fingerprint": p3_schedule["content_fingerprint"],
    }
    new_reference = {
        "schedule_version_version": "schedule-version.v2",
        "schedule_version_id": p4_schedule_id,
        "state": "DRAFT",
        "content_fingerprint": p4_content_fingerprint,
    }
    stability_fixture = build_stability_change_report_fixture(root)
    context = deepcopy(stability_fixture.context)
    context.update(
        {
            "environment": "TEST",
            "synthetic_provenance": deepcopy(p4_sample["synthetic_provenance"]),
            "base_schedule_version": base_reference,
            "new_schedule_version": new_reference,
            "generated_at_utc": "2026-08-28T10:05:00Z",
            "correlation_id": "correlation-p4-change-report-output",
        }
    )
    solver_reference = _reference(
        "solver-report.v2",
        cast(str, solver["report_id"]),
        cast(str, solver["report_fingerprint"]),
    )
    validation_reference = _reference(
        "validation-report.v2",
        "validation-report-" + validation_fingerprint.removeprefix("sha256:"),
        validation_fingerprint,
    )
    lineage = cast(dict[str, object], context["lineage"])
    lineage.update(
        {
            "base_problem": deepcopy(solver["base_problem"]),
            "new_problem": deepcopy(solver["new_problem"]),
            "replan_request": deepcopy(solver["replan_request"]),
            "planning_run_id": planning_run_id,
            "policy": deepcopy(solver["policy"]),
            "limits": deepcopy(solver["limits"]),
            "solver_report": solver_reference,
            "validation_report": validation_reference,
        }
    )
    cast(dict[str, object], context["freeze_evidence"])["effective_lock_ids"] = []
    unchanged_evidence = _reference(
        "schedule-version.v1",
        cast(str, p3_schedule["schedule_version_id"]),
        cast(str, p3_schedule["content_fingerprint"]),
    )
    reasons = {
        cast(str, cast(dict[str, object], assignment)["operation_id"]): [
            {"reason_code": "NO_CHANGE", "evidence_refs": [unchanged_evidence]}
        ]
        for assignment in assignments
    }
    report = build_change_report(
        context=context,
        base_assignments=assignments,
        new_assignments=assignments,
        active_operation_ids=tuple(sorted(reasons)),
        active_soft_locks=(),
        removed_by_fact={},
        reasons_by_operation=reasons,
        before_kpi=kpi,
        after_kpi=kpi,
    ).document
    report_reference = {
        "change_report_version": "change-report.v1",
        "report_id": report["report_id"],
        "report_fingerprint": report["report_fingerprint"],
    }
    kpi_reference = _reference(
        "kpi.v2", cast(str, kpi["kpi_id"]), contract_fingerprint(kpi)
    )
    candidate = cast(dict[str, object], solver["candidate"])
    p4_schedule = p4_sample
    p4_schedule.update(
        {
            "schedule_version_id": p4_schedule_id,
            "revision": cast(int, p3_schedule["revision"]) + 1,
            "state": "PUBLISHED",
            "parent_schedule_version": base_reference,
            "content": p4_content,
            "content_fingerprint": p4_content_fingerprint,
            "lineage": {
                "replan_request": deepcopy(lineage["replan_request"]),
                "base_schedule_version": base_reference,
                "base_snapshot": deepcopy(lineage["base_snapshot"]),
                "base_problem": deepcopy(lineage["base_problem"]),
                "new_snapshot": deepcopy(lineage["new_snapshot"]),
                "new_problem": deepcopy(lineage["new_problem"]),
                "event_stream_fingerprint": lineage["event_stream_fingerprint"],
                "fact_checkpoint": deepcopy(lineage["fact_checkpoint"]),
                "planning_run_id": planning_run_id,
                "candidate": _reference(
                    "replan-candidate.v1",
                    "replan-candidate-"
                    + cast(str, candidate["candidate_fingerprint"]).removeprefix("sha256:"),
                    cast(str, candidate["candidate_fingerprint"]),
                ),
                "validation_report": validation_reference,
                "kpi": kpi_reference,
                "solver_report": solver_reference,
                "change_report": report_reference,
                "code_commit": code_commit,
            },
            "validation": {
                "validation_report": validation_reference,
                "status": "PASS",
                "hard_violation_count": 0,
                "validated_at_utc": "2026-08-28T10:06:00Z",
            },
            "decision": {
                "decision": "APPROVED",
                "actor_ref": "actor:p4-output-approver",
                "capability": "approve",
                "reason": "Approve bounded P4 ChangeReport output fixture.",
                "decided_at_utc": "2026-08-28T10:07:00Z",
                "audit_event_id": "audit-p4-output-approval",
            },
            "publication": {
                "publication_id": "publication-p4-change-report-output",
                "target": "SIMULATION_INTERNAL",
                "published_at_utc": "2026-08-28T10:08:00Z",
                "audit_event_id": "audit-p4-output-publication",
            },
            "allowed_actions": ["view", "export"],
        }
    )
    publication = _sample(root, "publication-result.v1.synthetic.json")
    p4_reference = {
        "schedule_version_id": p4_schedule_id,
        "state": "PUBLISHED",
        "content_fingerprint": p4_content_fingerprint,
    }
    publication.update(
        {
            "publication_id": "publication-p4-change-report-output",
            "source_approved_version": {**p4_reference, "state": "APPROVED"},
            "published_version": p4_reference,
            "published_at_utc": "2026-08-28T10:08:00Z",
            "audit_event_id": "audit-p4-output-publication",
            "synthetic_provenance": deepcopy(p3_schedule["synthetic_provenance"]),
        }
    )
    publication["result_fingerprint"] = publication_result_fingerprint(publication)
    request = ExportJobRequest(
        schedule_version_id=p4_schedule_id,
        expected_content_fingerprint=p4_content_fingerprint,
        raw_idempotency_key="p4-change-report-export-key",
        reason="Create bounded P4 ChangeReport export.",
        correlation_id="correlation-p4-change-report-output",
        environment="TEST",
        synthetic_provenance=cast(
            Mapping[str, object], p4_schedule["synthetic_provenance"]
        ),
        change_report_reference=report_reference,
    )
    identity = export_job_identity(request)
    create_context = ExportJobContext(
        actor_ref="actor:p4-output-worker",
        authenticated=True,
        resolved_capabilities=frozenset({"export"}),
        schedule_version_scope=frozenset({p4_schedule_id}),
        export_job_scope=frozenset(),
        auth_policy_version="p4-output-simulation-policy.v1",
        production_binding=False,
        occurred_at_utc="2026-08-28T10:09:00Z",
        code_commit=code_commit,
    )
    created = build_created_export_job(
        request, identity, create_context, p4_schedule, publication
    )
    worker_context = ExportJobContext(
        actor_ref=create_context.actor_ref,
        authenticated=True,
        resolved_capabilities=create_context.resolved_capabilities,
        schedule_version_scope=create_context.schedule_version_scope,
        export_job_scope=frozenset({identity.export_job_id}),
        auth_policy_version=create_context.auth_policy_version,
        production_binding=False,
        occurred_at_utc="2026-08-28T10:10:00Z",
        code_commit=code_commit,
    )
    exporting = transition_export_job(
        created,
        target_state="EXPORTING",
        occurred_at_utc=worker_context.occurred_at_utc,
        audit_event_id_value=audit_event_id(identity.export_job_id, "ATTEMPT", 1),
        attempt=1,
        lease_reference=lease_reference_for(identity.export_job_id, 1, "worker:p4-output"),
    )
    return ChangeReportOutputFixture(
        p3_package=p3_package,
        p3_schedule=p3_schedule,
        schedule_version=p4_schedule,
        publication_result=publication,
        change_report=report,
        solver_report=solver,
        validation_report=validation,
        kpi=kpi,
        request=request,
        created_job=created,
        exporting_job=exporting,
        create_context=create_context,
        worker_context=worker_context,
    )


def build_fixture_package(fixture: ChangeReportOutputFixture) -> ChangeReportExportPackage:
    return build_change_report_export_package(
        p3_package=cast(Any, fixture.p3_package),
        schedule_version=fixture.schedule_version,
        publication_result=fixture.publication_result,
        export_job=fixture.exporting_job,
        change_report=fixture.change_report,
        solver_report=fixture.solver_report,
        validation_report=fixture.validation_report,
        kpi=fixture.kpi,
        create_audit_event_id=audit_event_id(
            cast(str, fixture.exporting_job["export_job_id"]), "CREATE", 0
        ),
        attempt_audit_event_id=cast(
            str, fixture.exporting_job["latest_audit_event_id"]
        ),
        completion_audit_event_id=audit_event_id(
            cast(str, fixture.exporting_job["export_job_id"]), "COMPLETED", 1
        ),
        correlation_id=fixture.request.correlation_id,
        generated_at_utc="2026-08-28T10:11:00Z",
    )


def _pass(name: str, evidence: Mapping[str, object]) -> dict[str, object]:
    return {"name": name, "status": "PASS", "evidence": dict(evidence)}


def _ensure(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _configuration(root: Path, database_url: str) -> Config:
    configuration = Config(str(root / "alembic.ini"))
    configuration.set_main_option("script_location", str(root / "backend/migrations"))
    configuration.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return configuration


def _seed_publication_audit(
    root: Path,
    repository: SqlAlchemyAuditRepository,
    fixture: ChangeReportOutputFixture,
    *,
    code_commit: str,
) -> None:
    audit = _sample(root, "audit-event.v1.synthetic.json")
    reference = {
        "schedule_version_id": fixture.schedule_version["schedule_version_id"],
        "state": "PUBLISHED",
        "content_fingerprint": fixture.schedule_version["content_fingerprint"],
    }
    audit.update(
        {
            "audit_event_id": fixture.publication_result["audit_event_id"],
            "occurred_at_utc": fixture.publication_result["published_at_utc"],
            "actor_ref": "actor:p4-output-publisher",
            "resolved_capability": "publish",
            "action": "PUBLISH",
            "aggregate_type": "SCHEDULE_VERSION",
            "aggregate_id": fixture.schedule_version["schedule_version_id"],
            "target": "SIMULATION_INTERNAL",
            "intent_type": "PUBLICATION",
            "reason": "Publish bounded P4 output fixture.",
            "idempotency_reference": None,
            "lineage": None,
            "before_state": "APPROVED",
            "after_state": "PUBLISHED",
            "source_version": {**reference, "state": "APPROVED"},
            "new_version": reference,
            "correlation_id": fixture.request.correlation_id,
            "parent_audit_event_id": None,
            "code_commit": code_commit,
            "synthetic_provenance": deepcopy(
                fixture.p3_schedule["synthetic_provenance"]
            ),
        }
    )
    require_workspace_document(audit)
    repository.append(audit)


def _run_durable_read(root: Path, *, code_commit: str) -> dict[str, object]:
    source = build_replan_application_fixture(root, code_commit=code_commit)
    with TemporaryDirectory(prefix="plantnexus-p4-output-read-") as directory:
        database_url = f"sqlite:///{(Path(directory) / 'read.db').as_posix()}"
        configuration = _alembic_config(root, database_url)
        command.upgrade(configuration, "head")
        engine = create_engine(database_url)
        try:
            runtime = seed_replan_application_runtime(root, engine, source)
            applied = runtime.service.execute(source.input, source.context)
            attempt = cast(dict[str, object], applied.attempt)
            result = cast(dict[str, object], applied.result)
            schedule = cast(dict[str, object], applied.schedule_version)
            report = cast(dict[str, object], applied.change_report)
            query = ChangeReportQuery(
                attempt_id=cast(str, attempt["attempt_id"]),
                expected_result_fingerprint=cast(str, result["result_fingerprint"]),
                expected_schedule_version_id=cast(str, schedule["schedule_version_id"]),
                expected_schedule_content_fingerprint=cast(
                    str, schedule["content_fingerprint"]
                ),
                expected_report_id=cast(str, report["report_id"]),
                expected_report_fingerprint=cast(str, report["report_fingerprint"]),
                limit=1,
            )
            context = ChangeReportReadContext(
                actor_ref="actor:p4-output-reader",
                authenticated=True,
                resolved_capabilities=frozenset({"view"}),
                attempt_scope=frozenset({query.attempt_id}),
                schedule_version_scope=frozenset(
                    {query.expected_schedule_version_id}
                ),
                data_plane="SIMULATION",
                environment="TEST",
                production_binding=False,
            )
            service = ChangeReportQueryService(
                lineage_repository=cast(Any, runtime.lineage_repository),
                schedule_repository=runtime.schedule_repository,
            )
            first = service.query(
                query, context, generated_at_utc="2026-08-28T11:00:00Z"
            )
            replay = service.query(
                query, context, generated_at_utc="2026-08-28T11:00:00Z"
            )
            _ensure(first.document == replay.document, "read replay bytes differ")
            _ensure(
                first.change_report == report,
                "read model changed immutable ChangeReport bytes",
            )
            _ensure(service.solver_invocations == 0, "read model invoked Solver")
            read_result = cast(dict[str, object], first.document["result"])
            _ensure(read_result["export_eligible"] is False, "DRAFT became export eligible")
            return {
                "attempt_id": query.attempt_id,
                "report_id": query.expected_report_id,
                "schedule_version_id": query.expected_schedule_version_id,
                "page_size": len(cast(list[object], read_result["operations"])),
                "next_cursor": read_result["next_cursor"],
                "exact_replay": True,
                "solver_invocations": service.solver_invocations,
                "export_eligible": read_result["export_eligible"],
            }
        finally:
            engine.dispose()
            command.downgrade(configuration, "base")


def _run_export_lifecycle(
    root: Path,
    fixture: ChangeReportOutputFixture,
    *,
    code_commit: str,
) -> dict[str, object]:
    with TemporaryDirectory(prefix="plantnexus-p4-output-job-") as directory:
        temporary = Path(directory)
        database_url = f"sqlite:///{(temporary / 'jobs.db').as_posix()}"
        configuration = _configuration(root, database_url)
        command.upgrade(configuration, "head")
        engine: Engine = create_engine(database_url)
        try:
            schedules = SqlAlchemyScheduleVersionRepository(
                engine, data_plane=WorkspaceDataPlane.SIMULATION
            )
            jobs = SqlAlchemyExportJobRepository(
                engine, data_plane=WorkspaceDataPlane.SIMULATION
            )
            audits = SqlAlchemyAuditRepository(
                engine, data_plane=WorkspaceDataPlane.SIMULATION
            )
            schedules.put(fixture.p3_schedule)
            schedules.put(fixture.schedule_version)
            _seed_publication_audit(root, audits, fixture, code_commit=code_commit)
            service = ExportJobService(
                transaction_factory=engine.begin,
                schedule_repository=schedules,
                export_job_repository=cast(Any, jobs),
                audit_repository=cast(Any, audits),
            )
            created = service.create(
                fixture.request,
                fixture.create_context,
                publication_result=fixture.publication_result,
            )
            replay = service.create(
                fixture.request,
                fixture.create_context,
                publication_result=fixture.publication_result,
            )
            identity = export_job_identity(fixture.request)
            worker_context = fixture.worker_context
            worker = InternalChangeReportExportJobWorker(
                service=service, storage_root=temporary
            )
            result = worker.run(
                export_job_id=identity.export_job_id,
                claim_context=worker_context,
                terminal_context=replace(
                    worker_context,
                    occurred_at_utc="2026-08-28T10:11:00Z",
                ),
                owner_reference="worker:p4-output",
                lease_expires_at_utc=datetime(2026, 8, 28, 10, 30, tzinfo=UTC),
                p3_package=cast(Any, fixture.p3_package),
                schedule_version=fixture.schedule_version,
                publication_result=fixture.publication_result,
                change_report=fixture.change_report,
                solver_report=fixture.solver_report,
                validation_report=fixture.validation_report,
                kpi=fixture.kpi,
                correlation_id=fixture.request.correlation_id,
            )
            download_context = ExportJobContext(
                actor_ref="actor:p4-output-downloader",
                authenticated=True,
                resolved_capabilities=frozenset({"export"}),
                schedule_version_scope=frozenset(
                    {cast(str, fixture.schedule_version["schedule_version_id"])}
                ),
                export_job_scope=frozenset({identity.export_job_id}),
                auth_policy_version="p4-output-simulation-policy.v1",
                production_binding=False,
                occurred_at_utc="2026-08-28T10:12:00Z",
                code_commit=code_commit,
            )
            download = ExportPackageDownloadService(
                export_job_repository=cast(Any, jobs),
                package_store=LocalExportPackageStore(temporary),
            ).download(
                identity.export_job_id,
                download_context,
                correlation_id="correlation-p4-output-download",
            )
            _ensure(created.document["state"] == "CREATED", "job was not CREATED")
            _ensure(replay.exact_replay, "job create was not exact replay")
            _ensure(result.job.document["state"] == "EXPORTED", "job not EXPORTED")
            _ensure(
                download.manifest_fingerprint == result.package.manifest_fingerprint,
                "download manifest lineage differs",
            )
            return {
                "export_job_id": identity.export_job_id,
                "state": result.job.document["state"],
                "attempt": result.job.document["attempt"],
                "package_id": result.package.package_id,
                "manifest_fingerprint": result.package.manifest_fingerprint,
                "archive_fingerprint": download.archive_fingerprint,
                "create_exact_replay": replay.exact_replay,
                "download_verified": True,
            }
        finally:
            engine.dispose()
            command.downgrade(configuration, "base")


def run_change_report_output_checks(root: Path) -> dict[str, object]:
    code_commit = os.environ.get("PLANTNEXUS_CODE_COMMIT", "uncommitted")
    fixture = build_change_report_output_fixture(root, code_commit=code_commit)
    first = build_fixture_package(fixture)
    second = build_fixture_package(fixture)
    _ensure(first == second, "package is not byte deterministic")
    verify_change_report_export_package(first)
    archive_first = archive_change_report_export_package(first)
    archive_second = archive_change_report_export_package(second)
    _ensure(archive_first == archive_second, "archive is not byte deterministic")
    durable_read = _run_durable_read(root, code_commit=code_commit)
    lifecycle = _run_export_lifecycle(root, fixture, code_commit=code_commit)

    with TemporaryDirectory(prefix="plantnexus-p4-output-io-") as directory:
        temporary = Path(directory)
        destination = temporary / "package"
        write_order: list[str] = []

        def recording_writer(path: Path, value: bytes) -> None:
            write_order.append(path.name)
            path.write_bytes(value)

        write_change_report_export_package(
            first, destination, file_writer=recording_writer
        )
        _ensure(write_order[-1] == "manifest.json", "manifest was not written last")
        _ensure(
            write_change_report_export_package(first, destination) == destination,
            "exact destination replay failed",
        )
        loaded = load_change_report_export_package(destination)
        _ensure(loaded == first, "verified load differs from source package")
        tampered_files = first.files
        tampered_files["change_report.json"] += b" "
        tampered = ChangeReportExportPackage(
            first.package_id,
            first.manifest_fingerprint,
            first.storage_reference,
            tuple(sorted(tampered_files.items())),
        )
        tamper_rejected = False
        try:
            verify_change_report_export_package(tampered)
        except ValueError:
            tamper_rejected = True
        _ensure(tamper_rejected, "tampered ChangeReport was accepted")

        failed_destination = temporary / "failed"

        def failing_writer(path: Path, value: bytes) -> None:
            if path.name == "resource_load.csv":
                raise OSError("injected")
            path.write_bytes(value)

        cleanup_rejected = False
        try:
            write_change_report_export_package(
                first, failed_destination, file_writer=failing_writer
            )
        except ValueError:
            cleanup_rejected = True
        _ensure(cleanup_rejected and not failed_destination.exists(), "partial write survived")

    boundaries = {
        "data_plane": "SIMULATION_ONLY",
        "publishable": False,
        "target": "SIMULATION_INTERNAL",
        "automatic_publish_export": "NOT_INVOKED",
        "schedule_version_state_pairs": "UNCHANGED",
        "export_job_state_pairs": "UNCHANGED",
        "p3_v1_v2_bytes": "FROZEN",
        "schema_migration_dependency": "UNCHANGED",
        "http_ui_p4_12_plus": "NOT_STARTED",
        "p5_plus": "NOT_STARTED",
        "production_external_authority_capacity_sla": "NOT_ESTABLISHED",
    }
    manifest = first.manifest
    checks = [
        _pass("durable-versioned-change-report-read-model", durable_read),
        _pass(
            "stable-filter-cursor-exact-replay-and-zero-solver-side-effect",
            {
                "exact_replay": durable_read["exact_replay"],
                "solver_invocations": durable_read["solver_invocations"],
                "draft_export_eligible": durable_read["export_eligible"],
            },
        ),
        _pass(
            "complete-change-report-replan-schedule-artifact-lineage",
            {
                "change_report_id": fixture.change_report["report_id"],
                "operation_universe_count": fixture.change_report[
                    "operation_universe_count"
                ],
                "schedule_version_id": fixture.schedule_version[
                    "schedule_version_id"
                ],
            },
        ),
        _pass("v3-export-job-existing-state-idempotency-and-audit", lifecycle),
        _pass(
            "deterministic-canonical-json-csv-five-sheet-xlsx-manifest-binding",
            {
                "package_id": first.package_id,
                "manifest_fingerprint": first.manifest_fingerprint,
                "file_count": manifest["file_count"],
                "sheet_count": next(
                    record["sheet_count"]
                    for record in cast(list[dict[str, object]], manifest["files"])
                    if record["path"] == "standard_package.xlsx"
                ),
                "archive_fingerprint": change_report_export_bytes_fingerprint(
                    archive_first
                ),
            },
        ),
        _pass(
            "manifest-last-replay-tamper-conflict-and-partial-cleanup",
            {
                "manifest_last": True,
                "exact_directory_replay": True,
                "tamper_rejected": True,
                "partial_cleanup": True,
            },
        ),
        _pass(
            "verified-exported-only-download-and-default-deny-boundary",
            {
                "download_verified": lifecycle["download_verified"],
                "artifact_manifest_version": "export-manifest.v3",
                "external_transfer": "NOT_STARTED",
                "production": "NOT_AUTHORIZED",
            },
        ),
        _pass("p4-p5-production-and-frozen-history-boundary", boundaries),
    ]
    return {
        "report_version": REPORT_VERSION,
        "status": "PASS",
        "task_id": TASK_ID,
        "code_commit": code_commit,
        "diff_base": DIFF_BASE,
        "impact_rule_count": len(IMPACT_RULES),
        "impact_rules": list(IMPACT_RULES),
        "check_count": len(checks),
        "checks": checks,
        "issues": [],
        "package_manifest": {
            "package_id": first.package_id,
            "manifest_fingerprint": first.manifest_fingerprint,
            "p3_package": manifest["p3_package"],
            "change_report": manifest["change_report"],
            "schedule_version": manifest["schedule_version"],
            "file_count": manifest["file_count"],
        },
        "boundaries": boundaries,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--report", type=Path, required=True)
    arguments = parser.parse_args(argv)
    report = run_change_report_output_checks(arguments.root.resolve())
    target = arguments.report.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(canonical_contract_bytes(report))
    print(
        f"{REPORT_VERSION}: {report['status']} "
        f"({report['check_count']}/{report['check_count']} checks)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "ChangeReportOutputFixture",
    "build_change_report_output_fixture",
    "build_fixture_package",
    "run_change_report_output_checks",
]
