"""Execute the TASK-DEMO-03 Showcase urgent-order chain and emit raw evidence."""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from hashlib import sha256
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from time import perf_counter
from typing import Any, cast


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEMO_ROOT = REPOSITORY_ROOT / "demo"
sys.path.insert(0, str(REPOSITORY_ROOT / "backend"))
sys.path.insert(0, str(DEMO_ROOT / "backend"))

from app.domain.execution_contracts import canonical_contract_bytes  # noqa: E402
from app.infrastructure.execution_event_repository import (  # noqa: E402
    SqlAlchemyExecutionEventRepository,
)
from app.infrastructure.publication_repository import (  # noqa: E402
    SqlAlchemyPublicationRepository,
)
from app.infrastructure.replan_repository import (  # noqa: E402
    SqlAlchemyReplanLineageRepository,
)
from app.infrastructure.schedule_version_repository import (  # noqa: E402
    SqlAlchemyScheduleVersionRepository,
)
from app.infrastructure.snapshot_repository import (  # noqa: E402
    SqlAlchemySnapshotRepository,
)
from app.infrastructure.workspace_persistence import (  # noqa: E402
    WorkspaceDataPlane,
)
from app.snapshots import SnapshotDataPlane  # noqa: E402
from plantnexus_demo.composition import create_demo_runtime  # noqa: E402
from plantnexus_demo.persistence import RunDatabase, key_reference  # noqa: E402
from plantnexus_demo.urgent import UrgentOrderCommand  # noqa: E402


REPORT_VERSION = "cnc-demo-replan-runtime-evidence.v1"


def _fingerprint(document: Mapping[str, object]) -> str:
    return f"sha256:{sha256(canonical_contract_bytes(document)).hexdigest()}"


def _count_rows(database: RunDatabase) -> dict[str, int]:
    tables = (
        "execution_event_ledger",
        "replan_projection_checkpoints",
        "replan_requests",
        "replan_request_events",
        "replan_attempts",
        "replan_results",
        "replan_audit_records",
        "schedule_versions",
        "demo_command_audit",
    )
    with database.engine.connect() as connection:
        return {
            table: cast(
                int,
                connection.exec_driver_sql(
                    f"SELECT COUNT(*) FROM {table}"
                ).scalar_one(),
            )
            for table in tables
        }


def build_report() -> dict[str, Any]:
    with TemporaryDirectory(prefix="plantnexus-demo-03-") as temporary:
        runtime = create_demo_runtime(
            repository_root=REPOSITORY_ROOT,
            runtime_root=Path(temporary) / "runtime",
            auto_resume_queued=False,
        )
        try:
            reset_started = perf_counter()
            reset = runtime.jobs.accept_reset(
                profile_name="showcase",
                idempotency_key="demo-03-evidence-reset-idempotency-0001",
                correlation_id="correlation-demo-03-evidence-reset",
            )
            reset_job = runtime.runner.wait(reset.job_id, timeout=90)
            reset_seconds = perf_counter() - reset_started
            if reset_job.status != "SUCCEEDED" or reset_job.result is None:
                raise RuntimeError("Showcase reset did not succeed")
            run_id = cast(str, reset_job.result["run_id"])

            plan_started = perf_counter()
            plan = runtime.jobs.accept_initial_plan(
                expected_run_id=run_id,
                idempotency_key="demo-03-evidence-plan-idempotency-0001",
                correlation_id="correlation-demo-03-evidence-plan",
            )
            plan_job = runtime.runner.wait(plan.job_id, timeout=90)
            plan_seconds = perf_counter() - plan_started
            if plan_job.status != "SUCCEEDED" or plan_job.result is None:
                raise RuntimeError("Showcase initial plan did not succeed")
            base_version_id = cast(str, plan_job.result["schedule_version_id"])
            base_fingerprint = cast(str, plan_job.result["content_fingerprint"])

            activation_started = perf_counter()
            activation = runtime.baseline.execute(
                expected_run_id=run_id,
                schedule_version_id=base_version_id,
                content_fingerprint=base_fingerprint,
                expected_state_revision=cast(int, plan_job.result["state_revision"]),
                confirmation="ACTIVATE_SIMULATION_BASELINE",
                idempotency_key_reference=key_reference(
                    "demo-03-evidence-activation-idempotency-0001"
                ),
                correlation_id="correlation-demo-03-evidence-activation",
                occurred_at_utc="2026-09-02T11:00:00Z",
            )
            activation_seconds = perf_counter() - activation_started

            command = UrgentOrderCommand(
                command_version="cnc-demo-urgent-order-command.v1",
                expected_run_id=run_id,
                expected_base_version_id=base_version_id,
                route_template_id="CNC-ROUTE-5",
                quantity=5,
                due_at_local="2026-09-09T18:00:00",
                priority_class="URGENT",
                note="Showcase 固定加急精密套筒",
            )
            urgent_key = "demo-03-evidence-urgent-idempotency-0001"
            urgent_started = perf_counter()
            accepted = runtime.jobs.accept_urgent_order(
                command=command,
                idempotency_key=urgent_key,
                correlation_id="correlation-demo-03-evidence-urgent",
            )
            urgent_job = runtime.runner.wait(accepted.job_id, timeout=120)
            urgent_seconds = perf_counter() - urgent_started
            if urgent_job.status != "SUCCEEDED" or urgent_job.result is None:
                raise RuntimeError(
                    f"Showcase urgent Replan failed: {urgent_job.error_code}"
                )

            replay_started = perf_counter()
            formal_replay = runtime.runner.urgent_replan.execute(
                command=command,
                idempotency_key_reference=key_reference(urgent_key),
                correlation_id="correlation-demo-03-evidence-urgent-replay",
                occurred_at_utc="2026-09-02T11:01:00Z",
            )
            replay_seconds = perf_counter() - replay_started
            active = runtime.control.active_run()
            if active is None:
                raise RuntimeError("active run disappeared")
            database = RunDatabase(
                repository_root=REPOSITORY_ROOT,
                database_path=runtime.paths.resolve_relative_database(
                    active.database_relative_path
                ),
            )
            try:
                plane = WorkspaceDataPlane.SIMULATION
                schedules = SqlAlchemyScheduleVersionRepository(
                    database.engine, data_plane=plane
                )
                publications = SqlAlchemyPublicationRepository(
                    database.engine, data_plane=plane
                )
                current = publications.get_current(target="SIMULATION_INTERNAL")
                base_schedule = schedules.get(base_version_id)
                draft = schedules.get(
                    cast(str, urgent_job.result["schedule_version_id"])
                )
                if base_schedule is None or draft is None:
                    raise RuntimeError("base or DRAFT ScheduleVersion is absent")
                lineage = SqlAlchemyReplanLineageRepository(
                    database.engine, data_plane=plane
                ).get_applied_result_for_attempt(
                    cast(str, urgent_job.result["attempt_id"])
                )
                if lineage is None:
                    raise RuntimeError("applied Replan lineage is absent")
                event = SqlAlchemyExecutionEventRepository(
                    database.engine, data_plane=plane
                ).get(cast(str, urgent_job.result["event_id"]))
                if event is None:
                    raise RuntimeError("urgent ExecutionEvent is absent")
                snapshots = SqlAlchemySnapshotRepository(
                    database.engine, data_plane=SnapshotDataPlane.SIMULATION
                )
                base_snapshot_ref = cast(
                    Mapping[str, object],
                    cast(Mapping[str, object], base_schedule["lineage"])["snapshot"],
                )
                base_snapshot = snapshots.get_by_id(
                    cast(str, base_snapshot_ref["artifact_id"])
                )
                new_snapshot = snapshots.get_by_id(
                    cast(str, urgent_job.result["snapshot_id"])
                )
                if base_snapshot is None or new_snapshot is None:
                    raise RuntimeError("Snapshot lineage is absent")
                base_completed = {
                    cast(str, item["operation_instance_id"]): canonical_contract_bytes(
                        item
                    )
                    for item in base_snapshot.document["operation_instances"]
                    if item["status"] == "COMPLETED"
                }
                new_completed = {
                    cast(str, item["operation_instance_id"]): canonical_contract_bytes(
                        item
                    )
                    for item in new_snapshot.document["operation_instances"]
                    if item["status"] == "COMPLETED"
                }
                operations = cast(
                    Sequence[Mapping[str, object]],
                    lineage.change_report["operations"],
                )
                classifications = Counter(
                    cast(str, operation["classification"])
                    for operation in operations
                )
                fact_evidence = cast(
                    Mapping[str, object],
                    lineage.validation_report["fact_lock_evidence"],
                )
                event_payload = cast(Mapping[str, object], event["payload"])
                with database.engine.connect() as connection:
                    audit_row = connection.exec_driver_sql(
                        "SELECT result_reference_json FROM demo_command_audit "
                        "WHERE command_type = 'URGENT_ORDER_REPLAN'"
                    ).first()
                if audit_row is None:
                    raise RuntimeError("Demo urgent command audit is absent")
                command_audit = json.loads(bytes(audit_row[0]).decode("utf-8"))
                row_counts = _count_rows(database)
                artifacts = database.list_artifacts()
            finally:
                database.close()

            state = runtime.story_state()
            current_unchanged = (
                current is not None
                and current.schedule_version_id == base_version_id
                and current.content_fingerprint == base_fingerprint
            )
            formal_event_is_exact = (
                set(event_payload)
                == {
                    "kind",
                    "demand_order_id",
                    "quantity",
                    "due_at_utc",
                    "priority_weight",
                    "priority_source",
                }
                and "route_template_id" not in event_payload
                and "note" not in event_payload
            )
            completed_preserved = base_completed == new_completed
            passed = (
                activation.state == "PUBLISHED"
                and urgent_job.result["schedule_state"] == "DRAFT"
                and urgent_job.result["solver_status"] in {"OPTIMAL", "FEASIBLE"}
                and urgent_job.result["validation_status"] == "PASS"
                and draft["schedule_version_version"] == "schedule-version.v2"
                and draft["state"] == "DRAFT"
                and current_unchanged
                and formal_replay.exact_replay
                and classifications["ADDED"] == 5
                and completed_preserved
                and cast(int, fact_evidence["running_fact_count"]) == 12
                and cast(int, fact_evidence["explicit_hard_lock_count"]) == 4
                and formal_event_is_exact
                and command_audit["command"]["route_template_id"] == "CNC-ROUTE-5"
                and state["story_state"] == "DRAFT_COMPARISON_READY"
                and row_counts["execution_event_ledger"] == 1
                and row_counts["replan_projection_checkpoints"] == 1
                and row_counts["replan_requests"] == 1
                and row_counts["replan_attempts"] == 1
                and row_counts["replan_results"] == 1
                and row_counts["schedule_versions"] == 2
            )
            report: dict[str, Any] = {
                "runtime_evidence_version": REPORT_VERSION,
                "generated_at_utc": datetime.now(UTC)
                .replace(microsecond=0)
                .isoformat()
                .replace("+00:00", "Z"),
                "task_id": "TASK-DEMO-03",
                "task_family": "demo-exclusive",
                "status": "PASS" if passed else "FAIL",
                "profile": "showcase",
                "run_id": run_id,
                "base_schedule": {
                    "schedule_version_id": base_version_id,
                    "content_fingerprint": base_fingerprint,
                    "state": activation.state,
                },
                "urgent_command": command.model_dump(mode="json"),
                "urgent_job": {
                    "job_id": urgent_job.job_id,
                    "status": urgent_job.status,
                    "attempt": urgent_job.attempt,
                    "stages": list(runtime.control.job_stages(urgent_job.job_id)),
                    "result": urgent_job.result,
                },
                "formal_replay": formal_replay.document,
                "current_publication": (
                    None
                    if current is None
                    else {
                        "schedule_version_id": current.schedule_version_id,
                        "content_fingerprint": current.content_fingerprint,
                        "unchanged": current_unchanged,
                    }
                ),
                "draft": {
                    "schedule_version_id": draft["schedule_version_id"],
                    "schedule_version_version": draft["schedule_version_version"],
                    "state": draft["state"],
                    "content_fingerprint": draft["content_fingerprint"],
                },
                "event": {
                    "event_id": event["event_id"],
                    "event_type": event["event_type"],
                    "source_position": event["source_position"],
                    "payload_fields": sorted(event_payload),
                    "formal_payload_exact": formal_event_is_exact,
                    "route_template_in_formal_event": False,
                },
                "projection": {
                    "completed_prebaseline_preserved": completed_preserved,
                    "completed_operation_count": len(base_completed),
                    "fact_lock_evidence": dict(fact_evidence),
                },
                "change_report": {
                    "report_id": lineage.change_report["report_id"],
                    "operation_universe_count": lineage.change_report[
                        "operation_universe_count"
                    ],
                    "classifications": dict(sorted(classifications.items())),
                    "stability": lineage.change_report["stability"],
                },
                "kpi": {
                    "before": lineage.change_report["before_kpi"],
                    "after": lineage.change_report["after_kpi"],
                    "delivery": lineage.kpi["delivery"],
                    "planning": lineage.kpi["planning"],
                },
                "row_counts": row_counts,
                "artifact_count": len(artifacts),
                "story_state": state["story_state"],
                "timings": {
                    "reset_seconds": reset_seconds,
                    "initial_plan_seconds": plan_seconds,
                    "activation_seconds": activation_seconds,
                    "urgent_replan_seconds": urgent_seconds,
                    "formal_exact_replay_seconds": replay_seconds,
                },
                "boundaries": {
                    "data_plane": "SIMULATION",
                    "production_authority": False,
                    "production_capacity_claim": "NOT_ESTABLISHED",
                    "single_showcase_run_not_p95": True,
                    "p7_registration": "NONE",
                },
            }
            report["report_fingerprint"] = _fingerprint(report)
            return report
        finally:
            runtime.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    arguments = parser.parse_args()
    report = build_report()
    arguments.report.parent.mkdir(parents=True, exist_ok=True)
    arguments.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "report": str(arguments.report.resolve()),
                "solver_status": report["urgent_job"]["result"]["solver_status"],
                "story_state": report["story_state"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
