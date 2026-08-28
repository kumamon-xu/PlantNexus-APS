"""Emit machine-checkable TASK-P4-08 result-application evidence."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.application.replan_application import (
    ReplanApplicationInput,
    ReplanApplicationService,
)
from app.domain.execution_contracts import (
    canonical_contract_bytes,
    contract_fingerprint,
    event_stream_fingerprint,
    replan_request_fingerprint,
    require_p4_document,
)
from app.domain.replan_application import ReplanApplicationContext
from app.domain.workspace_contracts import publication_result_fingerprint
from app.infrastructure.execution_event_repository import (
    SqlAlchemyExecutionEventRepository,
)
from app.infrastructure.publication_repository import (
    SqlAlchemyPublicationRepository,
)
from app.infrastructure.replan_persistence import (
    ArtifactReference,
    ProjectionCheckpoint,
)
from app.infrastructure.replan_repository import (
    SqlAlchemyProjectionCheckpointRepository,
    SqlAlchemyReplanAuditRepository,
    SqlAlchemyReplanLineageRepository,
    SqlAlchemyReplanRequestRepository,
)
from app.infrastructure.schedule_version_repository import (
    SqlAlchemyScheduleVersionRepository,
)
from app.infrastructure.snapshot_repository import SqlAlchemySnapshotRepository
from app.infrastructure.workspace_persistence import WorkspaceDataPlane
from app.planning.backends.cp_sat.replan_solver_check import _limits
from app.planning.policy.contracts import SolveLimitsDocument
from app.planning.problem.contracts import DemandPriorityInput
from app.planning.problem.freeze_projection import project_effective_locks
from app.planning.problem.freeze_window_check import (
    TICK_SECONDS,
    _primary_events,
    _scope,
    build_freeze_window_fixture,
)
from app.snapshots.contracts import SnapshotDataPlane


REPORT_VERSION = "p4-replan-application-report.v1"
TASK_ID = "TASK-P4-08"
DIFF_BASE = "77981f0564d91dfb57fee6e3792f4989bdb51d32"
IMPACT_RULES = (
    "IMPACT-APPLICATION",
    "IMPACT-DOCS",
    "IMPACT-DOMAIN",
    "IMPACT-INFRA",
    "IMPACT-STATE",
    "IMPACT-TESTS",
)


@dataclass(frozen=True, slots=True)
class ReplanApplicationFixture:
    """Frozen synthetic documents used by tests and the provider artifact."""

    base_snapshot: object
    snapshot: object
    base_schedule: dict[str, object]
    events: tuple[dict[str, object], ...]
    checkpoint: ProjectionCheckpoint
    request: dict[str, object]
    priority_facts: dict[str, DemandPriorityInput]
    policy: dict[str, object]
    limits: SolveLimitsDocument
    before_kpi: dict[str, object]
    after_kpi: dict[str, object]
    context: ReplanApplicationContext
    problem_builder_version: str
    tick_seconds: int
    horizon_start_utc: str
    horizon_end_utc: str

    @property
    def input(self) -> ReplanApplicationInput:
        return ReplanApplicationInput(
            request=self.request,
            priority_facts=self.priority_facts,
            problem_builder_version=self.problem_builder_version,
            tick_seconds=self.tick_seconds,
            horizon_start_utc=self.horizon_start_utc,
            horizon_end_utc=self.horizon_end_utc,
            policy=self.policy,
            limits=self.limits,
            before_kpi=self.before_kpi,
            after_kpi=self.after_kpi,
        )


@dataclass(frozen=True, slots=True)
class ReplanApplicationRuntime:
    """Actual repositories behind one isolated application-service fixture."""

    service: ReplanApplicationService
    schedule_repository: SqlAlchemyScheduleVersionRepository
    publication_repository: SqlAlchemyPublicationRepository
    snapshot_repository: SqlAlchemySnapshotRepository
    request_repository: SqlAlchemyReplanRequestRepository
    lineage_repository: SqlAlchemyReplanLineageRepository
    audit_repository: SqlAlchemyReplanAuditRepository


def _sample(root: Path, name: str) -> dict[str, object]:
    return cast(
        dict[str, object],
        json.loads((root / "schemas/samples" / name).read_text(encoding="utf-8")),
    )


def _format_utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _artifact(
    *, document_version: str, artifact_id: str, fingerprint: str
) -> dict[str, object]:
    return {
        "document_version": document_version,
        "artifact_id": artifact_id,
        "fingerprint": fingerprint,
    }


def _priority_facts(snapshot: object) -> dict[str, DemandPriorityInput]:
    document = cast(Mapping[str, object], getattr(snapshot, "document"))
    records = cast(Mapping[str, object], document["records"])
    demands = cast(Sequence[Mapping[str, object]], records["demand_orders"])
    return {
        cast(str, demand["demand_order_id"]): {
            "priority_weight": 2,
            "source_system": "plantnexus-synthetic-policy",
            "source_version": "1.0.0",
            "source_record_id": (
                f"SIM-P4-FREEZE-PRIORITY-{demand['demand_order_id']}"
            ),
        }
        for demand in demands
    }


def _kpi(
    root: Path,
    *,
    planning_run_id: str,
    makespan_seconds: int,
) -> dict[str, object]:
    document = _sample(root, "kpi.v2.synthetic.json")
    document["planning_run_id"] = planning_run_id
    planning = cast(dict[str, object], document["planning"])
    planning.update(
        {
            "makespan_seconds": makespan_seconds,
            "scheduled_operation_count": 2,
            "unscheduled_operation_count": 0,
        }
    )
    document.pop("kpi_id")
    document["kpi_id"] = "kpi-" + sha256(
        canonical_contract_bytes(document)
    ).hexdigest()
    return document


def _limits_reference(limits: SolveLimitsDocument) -> dict[str, object]:
    return {
        "solve_limits_version": limits["solve_limits_version"],
        "limits_id": limits["limits_id"],
        "limits_revision": limits["limits_revision"],
        "limits_fingerprint": contract_fingerprint(limits),
        "max_wall_time_seconds": limits["max_wall_time_seconds"],
        "max_workers": limits["max_workers"],
        "random_seed": limits["random_seed"],
    }


def _checkpoint(request: Mapping[str, object]) -> ProjectionCheckpoint:
    stream = cast(Mapping[str, object], request["event_stream"])
    authority = cast(Mapping[str, object], stream["authority"])
    source_stream = cast(Mapping[str, object], stream["source_stream"])
    fact = cast(Mapping[str, object], stream["fact_checkpoint"])
    return ProjectionCheckpoint(
        factory_id=cast(str, request["factory_id"]),
        planning_scope_id=cast(str, request["planning_scope_id"]),
        authority_id=cast(str, authority["authority_id"]),
        stream_id=cast(str, source_stream["stream_id"]),
        stream_version=cast(str, source_stream["stream_version"]),
        last_applied_position=cast(int, stream["through_position"]),
        prefix_fingerprint=cast(str, stream["stream_fingerprint"]),
        fact_checkpoint=ArtifactReference(
            document_version=cast(str, fact["document_version"]),
            artifact_id=cast(str, fact["artifact_id"]),
            fingerprint=cast(str, fact["fingerprint"]),
        ),
        updated_at_utc=cast(str, request["requested_at_utc"]),
    )


def build_replan_application_fixture(
    root: Path,
    *,
    code_commit: str = "uncommitted",
) -> ReplanApplicationFixture:
    """Build one exact P4-03..07 lineage without introducing new defaults."""

    frozen = build_freeze_window_fixture(root)
    base_schedule = cast(dict[str, object], deepcopy(frozen.base_schedule))
    context = ReplanApplicationContext(
        data_plane="SIMULATION",
        environment="TEST",
        production_binding=False,
        actor_ref="actor:sim-p4-08-planner",
        idempotency_key_reference=contract_fingerprint(
            {"task": TASK_ID, "command": "apply-replan"}
        ),
        correlation_id="correlation-p4-08-application-001",
        occurred_at_utc="2026-08-28T06:00:00Z",
        planning_run_id="planning-run-p4-08-application-001",
        attempt_number=1,
        code_commit=code_commit,
    )
    before_kpi = _kpi(
        root,
        planning_run_id="planning-run-p4-freeze-base-001",
        makespan_seconds=720,
    )
    after_kpi = _kpi(
        root,
        planning_run_id=context.planning_run_id,
        makespan_seconds=720,
    )
    base_lineage = cast(dict[str, object], base_schedule["lineage"])
    base_lineage["kpi"] = _artifact(
        document_version="kpi.v2",
        artifact_id=cast(str, before_kpi["kpi_id"]),
        fingerprint=contract_fingerprint(before_kpi),
    )
    projection = project_effective_locks(
        snapshot=frozen.snapshot,
        problem=frozen.problem,
        base_schedule=base_schedule,
        policy=frozen.policy,
    ).document

    instances = cast(
        Sequence[Mapping[str, object]],
        frozen.base_snapshot.document["operation_instances"],
    )
    scope = _scope(frozen.base_snapshot, "primary")
    events = tuple(
        cast(dict[str, object], deepcopy(value))
        for value in _primary_events(scope, instances[0], instances[1])
    )
    event_fingerprints = [cast(str, value["event_fingerprint"]) for value in events]
    first_event = events[0]
    request = _sample(root, "replan-request.v1.synthetic.json")
    request.update(
        {
            "factory_id": scope.factory_id,
            "planning_scope_id": scope.planning_scope_id,
            "base_schedule_version": deepcopy(projection["base_schedule_version"]),
            "base_snapshot": deepcopy(base_lineage["snapshot"]),
            "base_problem": deepcopy(base_lineage["problem"]),
            "new_snapshot": deepcopy(projection["new_snapshot"]),
            "new_snapshot_cutoff_at_utc": frozen.snapshot.document["cutoff_at_utc"],
            "new_problem": deepcopy(projection["new_problem"]),
            "event_stream": {
                "authority": deepcopy(first_event["authority"]),
                "source_stream": deepcopy(first_event["source_stream"]),
                "from_position": 1,
                "through_position": len(events),
                "event_ids": [value["event_id"] for value in events],
                "event_fingerprints": event_fingerprints,
                "stream_fingerprint": event_stream_fingerprint(event_fingerprints),
                "fact_checkpoint": _artifact(
                    document_version="execution-fact-checkpoint.v1",
                    artifact_id="fact-checkpoint-p4-08-application-001",
                    fingerprint=contract_fingerprint(
                        {
                            "snapshot_id": frozen.snapshot.snapshot_id,
                            "stream": event_fingerprints,
                        }
                    ),
                ),
            },
            "trigger_event_ids": [first_event["event_id"]],
            "trigger_reason": "EXECUTION_FACT_CHANGED",
            "freeze_resolution": deepcopy(projection["freeze_resolution"]),
            "planning_policy": deepcopy(projection["planning_policy"]),
            "solve_limits": _limits_reference(_limits()),
            "synthetic_provenance": deepcopy(first_event["synthetic_provenance"]),
            "requested_at_utc": context.occurred_at_utc,
            "correlation_id": context.correlation_id,
        }
    )
    request["request_fingerprint"] = replan_request_fingerprint(request)
    request["request_id"] = "replan-request-" + cast(
        str, request["request_fingerprint"]
    ).removeprefix("sha256:")
    require_p4_document(request)
    checkpoint = _checkpoint(request)
    horizon_start = cast(str, frozen.snapshot.document["cutoff_at_utc"])
    horizon_end = _format_utc(
        datetime.fromisoformat(horizon_start.replace("Z", "+00:00"))
        + timedelta(days=1)
    )
    return ReplanApplicationFixture(
        base_snapshot=frozen.base_snapshot,
        snapshot=frozen.snapshot,
        base_schedule=base_schedule,
        events=events,
        checkpoint=checkpoint,
        request=request,
        priority_facts=_priority_facts(frozen.snapshot),
        policy=frozen.policy,
        limits=_limits(),
        before_kpi=before_kpi,
        after_kpi=after_kpi,
        context=context,
        problem_builder_version=cast(
            str, frozen.problem.document["problem_builder_version"]
        ),
        tick_seconds=TICK_SECONDS,
        horizon_start_utc=horizon_start,
        horizon_end_utc=horizon_end,
    )


def _publication(
    root: Path, base_schedule: Mapping[str, object]
) -> dict[str, object]:
    document = _sample(root, "publication-result.v1.synthetic.json")
    schedule_id = cast(str, base_schedule["schedule_version_id"])
    content_fingerprint = cast(str, base_schedule["content_fingerprint"])
    document.update(
        {
            "publication_id": "publication-p4-08-base-001",
            "source_approved_version": {
                "schedule_version_id": schedule_id,
                "state": "APPROVED",
                "content_fingerprint": content_fingerprint,
            },
            "published_version": {
                "schedule_version_id": schedule_id,
                "state": "PUBLISHED",
                "content_fingerprint": content_fingerprint,
            },
            "previous_current_version": None,
            "superseded_version": None,
            "published_at_utc": "2026-08-19T00:14:00Z",
            "audit_event_id": "audit-p4-08-base-publication-001",
        }
    )
    idempotency = cast(dict[str, object], document["idempotency_reference"])
    idempotency.update(
        {
            "scope": f"SIMULATION/PUBLISH/{schedule_id}/SIMULATION_INTERNAL",
            "key_reference": contract_fingerprint(
                {"task": TASK_ID, "publication": schedule_id}
            ),
            "request_fingerprint": contract_fingerprint(
                {"task": TASK_ID, "published": content_fingerprint}
            ),
        }
    )
    document["result_fingerprint"] = publication_result_fingerprint(document)
    return document


def seed_replan_application_runtime(
    root: Path,
    engine: Engine,
    fixture: ReplanApplicationFixture,
) -> ReplanApplicationRuntime:
    """Seed all immutable inputs, then expose the actual P4 repositories."""

    schedule_repository = SqlAlchemyScheduleVersionRepository(
        engine, data_plane=WorkspaceDataPlane.SIMULATION
    )
    publication_repository = SqlAlchemyPublicationRepository(
        engine, data_plane=WorkspaceDataPlane.SIMULATION
    )
    snapshot_repository = SqlAlchemySnapshotRepository(
        engine, data_plane=SnapshotDataPlane.SIMULATION
    )
    request_repository = SqlAlchemyReplanRequestRepository(
        engine, data_plane=WorkspaceDataPlane.SIMULATION
    )
    lineage_repository = SqlAlchemyReplanLineageRepository(
        engine, data_plane=WorkspaceDataPlane.SIMULATION
    )
    audit_repository = SqlAlchemyReplanAuditRepository(
        engine, data_plane=WorkspaceDataPlane.SIMULATION
    )
    schedule_repository.put(fixture.base_schedule)
    snapshot_repository.put(cast(object, fixture.base_snapshot))  # type: ignore[arg-type]
    snapshot_repository.put(cast(object, fixture.snapshot))  # type: ignore[arg-type]
    event_repository = SqlAlchemyExecutionEventRepository(
        engine, data_plane=WorkspaceDataPlane.SIMULATION
    )
    for event in fixture.events:
        event_repository.append(event)
    SqlAlchemyProjectionCheckpointRepository(
        engine, data_plane=WorkspaceDataPlane.SIMULATION
    ).put_initial(fixture.checkpoint)
    publication_repository.persist_and_set_current(
        _publication(root, fixture.base_schedule), expected_current=None
    )
    service = ReplanApplicationService(
        transaction_factory=engine.begin,
        schedule_repository=schedule_repository,
        publication_repository=publication_repository,
        snapshot_repository=snapshot_repository,
        request_repository=request_repository,
        lineage_repository=lineage_repository,
        audit_repository=audit_repository,
    )
    return ReplanApplicationRuntime(
        service=service,
        schedule_repository=schedule_repository,
        publication_repository=publication_repository,
        snapshot_repository=snapshot_repository,
        request_repository=request_repository,
        lineage_repository=lineage_repository,
        audit_repository=audit_repository,
    )


def _alembic_config(root: Path, database_url: str) -> Config:
    configuration = Config(str(root / "alembic.ini"))
    configuration.set_main_option(
        "script_location", str(root / "backend" / "migrations")
    )
    configuration.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return configuration


def _pass(check_id: str, evidence: Mapping[str, object]) -> dict[str, object]:
    return {"check_id": check_id, "status": "PASS", "evidence": dict(evidence)}


def _ensure(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _row_counts(engine: Engine) -> dict[str, int]:
    names = (
        "replan_requests",
        "replan_attempts",
        "replan_results",
        "replan_audit_records",
        "schedule_versions",
    )
    with engine.connect() as connection:
        return {
            name: cast(
                int,
                connection.execute(text(f"SELECT count(*) FROM {name}")).scalar_one(),
            )
            for name in names
        }


def run_replan_application_checks(root: Path) -> dict[str, object]:
    """Exercise the real two-transaction boundary and exact durable replay."""

    code_commit = os.environ.get("PLANTNEXUS_CODE_COMMIT", "uncommitted")
    fixture = build_replan_application_fixture(root, code_commit=code_commit)
    base_bytes = canonical_contract_bytes(fixture.base_schedule)
    with TemporaryDirectory(prefix="plantnexus-p4-replan-application-") as directory:
        database_path = Path(directory) / "replan-application.db"
        database_url = f"sqlite:///{database_path.as_posix()}"
        configuration = _alembic_config(root, database_url)
        command.upgrade(configuration, "head")
        engine = create_engine(database_url)
        try:
            runtime = seed_replan_application_runtime(root, engine, fixture)
            first = runtime.service.execute(fixture.input, fixture.context)
            replay = runtime.service.execute(fixture.input, fixture.context)
            _ensure(first.schedule_version is not None, "new DRAFT is absent")
            _ensure(first.change_report is not None, "ChangeReport is absent")
            _ensure(first.validation_report is not None, "fresh validation is absent")
            _ensure(first.solver_report is not None, "SolverReport is absent")
            _ensure(first.exact_replay is False, "first apply reported a replay")
            _ensure(replay.exact_replay is True, "second apply was not exact replay")
            _ensure(
                canonical_contract_bytes(first.schedule_version)
                == canonical_contract_bytes(replay.schedule_version),
                "replay returned different DRAFT bytes",
            )
            _ensure(
                canonical_contract_bytes(first.change_report)
                == canonical_contract_bytes(replay.change_report),
                "replay returned different ChangeReport bytes",
            )
            draft = cast(dict[str, object], first.schedule_version)
            _ensure(draft["state"] == "DRAFT", "application advanced beyond DRAFT")
            _ensure(
                draft["parent_schedule_version"]
                == fixture.request["base_schedule_version"],
                "DRAFT parent is not the exact PUBLISHED base",
            )
            stored_base = runtime.schedule_repository.get(
                cast(str, fixture.base_schedule["schedule_version_id"])
            )
            _ensure(
                stored_base is not None
                and canonical_contract_bytes(stored_base) == base_bytes,
                "PUBLISHED base changed during result application",
            )
            current = runtime.publication_repository.get_current()
            _ensure(
                current is not None
                and current.schedule_version_id
                == fixture.base_schedule["schedule_version_id"],
                "application changed the current publication",
            )
            counts = _row_counts(engine)
            _ensure(
                counts
                == {
                    "replan_requests": 1,
                    "replan_attempts": 1,
                    "replan_results": 1,
                    "replan_audit_records": 3,
                    "schedule_versions": 2,
                },
                "transaction/replay row counts differ",
            )
            stored = runtime.lineage_repository.get_applied_result_for_attempt(
                cast(str, first.attempt["attempt_id"])
            )
            _ensure(stored is not None, "full applied-result envelope is absent")
            _ensure(
                stored is not None
                and stored.change_report == first.change_report
                and stored.solver_report == first.solver_report,
                "durable applied-result artifacts differ",
            )
        finally:
            engine.dispose()
            command.downgrade(configuration, "base")

    boundaries = {
        "data_plane": "SIMULATION_ONLY",
        "result_schedule_state": "DRAFT_ONLY",
        "base_published_schedule": "BYTE_EXACT_IMMUTABLE",
        "approval_publish_export": "NOT_INVOKED",
        "http_ui_execution_simulator": "NOT_IMPLEMENTED_BY_TASK",
        "p4_09_plus": "NOT_STARTED",
        "p5_plus": "NOT_STARTED",
        "production_external_authority_capacity_sla": "NOT_ESTABLISHED",
    }
    draft = cast(dict[str, object], first.schedule_version)
    report = cast(dict[str, object], first.change_report)
    checks = [
        _pass(
            "exact-published-base-snapshot-problem-event-policy-limits-lineage",
            {
                "request_id": fixture.request["request_id"],
                "event_count": len(fixture.events),
                "base_schedule_version_id": fixture.base_schedule[
                    "schedule_version_id"
                ],
            },
        ),
        _pass(
            "request-attempt-and-audit-intent-transaction",
            {
                "attempt_id": first.attempt["attempt_id"],
                "request_replayed_on_second_call": replay.request_replayed,
                "attempt_replayed_on_second_call": replay.attempt_replayed,
            },
        ),
        _pass(
            "global-solver-and-fresh-independent-validation",
            {
                "solver_report_id": cast(dict[str, object], first.solver_report)[
                    "report_id"
                ],
                "validation_status": cast(
                    dict[str, object], first.validation_report
                )["status"],
                "hard_violation_count": cast(
                    dict[str, object], first.validation_report
                )["hard_violation_count"],
            },
        ),
        _pass(
            "complete-change-report-and-obj-002-precheck",
            {
                "change_report_id": report["report_id"],
                "operation_universe_count": report["operation_universe_count"],
                "stability": report["stability"],
            },
        ),
        _pass(
            "atomic-draft-result-envelope-and-result-audit",
            {
                "schedule_version_id": draft["schedule_version_id"],
                "schedule_state": draft["state"],
                "result_id": first.result["result_id"],
                "row_counts": counts,
            },
        ),
        _pass(
            "byte-exact-replay-without-resolve-or-new-version",
            {
                "exact_replay": replay.exact_replay,
                "result_replayed": replay.result_replayed,
                "schedule_version_count": counts["schedule_versions"],
            },
        ),
        _pass(
            "published-base-and-current-reference-remain-immutable",
            {
                "base_fingerprint": fixture.base_schedule["content_fingerprint"],
                "base_state": fixture.base_schedule["state"],
                "current_reference_changed": False,
            },
        ),
        _pass("p4-p5-production-capability-boundary", boundaries),
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
        "counts": {
            "execution_events": len(fixture.events),
            "replan_requests": counts["replan_requests"],
            "replan_attempts": counts["replan_attempts"],
            "replan_results": counts["replan_results"],
            "audit_records": counts["replan_audit_records"],
            "schedule_versions_total": counts["schedule_versions"],
            "new_draft_schedule_versions": 1,
            "exact_replays": 1,
            "machine_checks": len(checks),
        },
        "transaction_manifest": {
            "request_id": fixture.request["request_id"],
            "request_fingerprint": fixture.request["request_fingerprint"],
            "attempt_id": first.attempt["attempt_id"],
            "result_id": first.result["result_id"],
            "base_schedule_version_id": fixture.base_schedule["schedule_version_id"],
            "new_schedule_version_id": draft["schedule_version_id"],
            "new_content_fingerprint": draft["content_fingerprint"],
            "solver_report_id": cast(dict[str, object], first.solver_report)[
                "report_id"
            ],
            "validation_report_fingerprint": contract_fingerprint(
                cast(dict[str, object], first.validation_report)
            ),
            "change_report_id": report["report_id"],
            "change_report_fingerprint": report["report_fingerprint"],
        },
        "boundaries": boundaries,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--report", type=Path, required=True)
    arguments = parser.parse_args(argv)
    try:
        report = run_replan_application_checks(arguments.root.resolve())
    except Exception as error:
        report = {
            "report_version": REPORT_VERSION,
            "status": "FAIL",
            "task_id": TASK_ID,
            "code_commit": os.environ.get("PLANTNEXUS_CODE_COMMIT", "uncommitted"),
            "diff_base": DIFF_BASE,
            "impact_rule_count": len(IMPACT_RULES),
            "impact_rules": list(IMPACT_RULES),
            "error_type": type(error).__name__,
            "error_message": "replan application evidence check failed",
            "issues": ["machine-check-failed"],
        }
        exit_code = 1
    else:
        exit_code = 0
    arguments.report.parent.mkdir(parents=True, exist_ok=True)
    arguments.report.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "DIFF_BASE",
    "IMPACT_RULES",
    "REPORT_VERSION",
    "TASK_ID",
    "ReplanApplicationFixture",
    "ReplanApplicationRuntime",
    "build_replan_application_fixture",
    "main",
    "run_replan_application_checks",
    "seed_replan_application_runtime",
]
