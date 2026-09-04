"""Run one TASK-DEMO-04 Showcase chain and emit B5 presentation evidence."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from datetime import UTC, datetime
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import sys
from tempfile import TemporaryDirectory
from time import perf_counter
from typing import Any, cast

import ortools


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEMO_ROOT = REPOSITORY_ROOT / "demo"
sys.path.insert(0, str(REPOSITORY_ROOT / "backend"))
sys.path.insert(0, str(DEMO_ROOT / "backend"))

from app.infrastructure.publication_repository import (  # noqa: E402
    SqlAlchemyPublicationRepository,
)
from app.infrastructure.workspace_persistence import (  # noqa: E402
    WorkspaceDataPlane,
)
from plantnexus_demo.composition import create_demo_runtime  # noqa: E402
from plantnexus_demo.persistence import RunDatabase, key_reference  # noqa: E402
from plantnexus_demo.presentation import (  # noqa: E402
    ComparisonPresentationQuery,
    SchedulePresentationQuery,
    presentation_contract_schemas,
)
from plantnexus_demo.urgent import UrgentOrderCommand  # noqa: E402


REPORT_VERSION = "cnc-demo-presentation-runtime-evidence.v1"


def _fingerprint(document: Mapping[str, object]) -> str:
    payload = json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return "sha256:" + sha256(payload).hexdigest()


def _json_bytes(document: object) -> int:
    return len(
        json.dumps(
            document,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    )


def _time(call: Any) -> tuple[Any, float]:
    started = perf_counter()
    value = call()
    return value, perf_counter() - started


def _counts(database: RunDatabase) -> dict[str, int]:
    tables = (
        "schedule_versions",
        "publication_current_references",
        "replan_requests",
        "replan_attempts",
        "replan_results",
        "demo_artifacts",
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
    with TemporaryDirectory(prefix="plantnexus-demo-04-") as temporary:
        runtime = create_demo_runtime(
            repository_root=REPOSITORY_ROOT,
            runtime_root=Path(temporary) / "runtime",
            auto_resume_queued=False,
        )
        try:
            reset, reset_seconds = _time(
                lambda: runtime.jobs.accept_reset(
                    profile_name="showcase",
                    idempotency_key="demo-04-evidence-reset-idempotency-0001",
                    correlation_id="correlation-demo-04-evidence-reset",
                )
            )
            reset_job, reset_wait_seconds = _time(
                lambda: runtime.runner.wait(reset.job_id, timeout=90)
            )
            if reset_job.status != "SUCCEEDED" or reset_job.result is None:
                raise RuntimeError("Showcase reset did not succeed")
            run_id = cast(str, reset_job.result["run_id"])

            plan, plan_accept_seconds = _time(
                lambda: runtime.jobs.accept_initial_plan(
                    expected_run_id=run_id,
                    idempotency_key="demo-04-evidence-plan-idempotency-0001",
                    correlation_id="correlation-demo-04-evidence-plan",
                )
            )
            plan_job, plan_wait_seconds = _time(
                lambda: runtime.runner.wait(plan.job_id, timeout=90)
            )
            if plan_job.status != "SUCCEEDED" or plan_job.result is None:
                raise RuntimeError("Showcase initial plan did not succeed")
            base_version_id = cast(str, plan_job.result["schedule_version_id"])
            runtime.baseline.execute(
                expected_run_id=run_id,
                schedule_version_id=base_version_id,
                content_fingerprint=cast(
                    str, plan_job.result["content_fingerprint"]
                ),
                expected_state_revision=cast(
                    int, plan_job.result["state_revision"]
                ),
                confirmation="ACTIVATE_SIMULATION_BASELINE",
                idempotency_key_reference=key_reference(
                    "demo-04-evidence-activate-idempotency-0001"
                ),
                correlation_id="correlation-demo-04-evidence-activate",
                occurred_at_utc="2026-09-02T11:00:00Z",
            )
            command = UrgentOrderCommand(
                command_version="cnc-demo-urgent-order-command.v1",
                expected_run_id=run_id,
                expected_base_version_id=base_version_id,
                route_template_id="CNC-ROUTE-5",
                quantity=5,
                due_at_local="2026-09-09T18:00:00",
                priority_class="URGENT",
                note="Showcase presentation evidence",
            )
            urgent, urgent_accept_seconds = _time(
                lambda: runtime.jobs.accept_urgent_order(
                    command=command,
                    idempotency_key="demo-04-evidence-urgent-idempotency-0001",
                    correlation_id="correlation-demo-04-evidence-urgent",
                )
            )
            urgent_job, urgent_wait_seconds = _time(
                lambda: runtime.runner.wait(urgent.job_id, timeout=120)
            )
            if urgent_job.status != "SUCCEEDED" or urgent_job.result is None:
                raise RuntimeError("Showcase urgent Replan did not succeed")
            draft_version_id = cast(
                str, urgent_job.result["schedule_version_id"]
            )
            request_id = cast(str, urgent_job.result["request_id"])

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
                before_counts = _counts(database)
                before_state = runtime.story_state()
                current = SqlAlchemyPublicationRepository(
                    database.engine, data_plane=WorkspaceDataPlane.SIMULATION
                ).get_current(target="SIMULATION_INTERNAL")

                factory, factory_seconds = _time(runtime.presentation.factory)
                base_page, base_seconds = _time(
                    lambda: runtime.presentation.schedule(
                        base_version_id,
                        SchedulePresentationQuery(limit=500),
                    )
                )
                base_tail, base_tail_seconds = _time(
                    lambda: runtime.presentation.schedule(
                        base_version_id,
                        SchedulePresentationQuery(offset=500, limit=500),
                    )
                )
                draft_page, draft_seconds = _time(
                    lambda: runtime.presentation.schedule(
                        draft_version_id,
                        SchedulePresentationQuery(limit=500),
                    )
                )
                draft_tail, draft_tail_seconds = _time(
                    lambda: runtime.presentation.schedule(
                        draft_version_id,
                        SchedulePresentationQuery(offset=500, limit=500),
                    )
                )
                comparison, comparison_seconds = _time(
                    lambda: runtime.presentation.comparison(request_id)
                )
                all_classes = (
                    "ADDED",
                    "CHANGED",
                    "REMOVED_BY_FACT",
                    "UNCHANGED",
                )
                comparison_all, comparison_all_seconds = _time(
                    lambda: runtime.presentation.comparison(
                        request_id,
                        ComparisonPresentationQuery(
                            classifications=all_classes,
                            limit=500,
                        ),
                    )
                )
                comparison_tail, comparison_tail_seconds = _time(
                    lambda: runtime.presentation.comparison(
                        request_id,
                        ComparisonPresentationQuery(
                            classifications=all_classes,
                            offset=500,
                            limit=500,
                        ),
                    )
                )
                first_resource = draft_page.assignments[0].resource_id
                filtered, filtered_seconds = _time(
                    lambda: runtime.presentation.schedule(
                        draft_version_id,
                        SchedulePresentationQuery(
                            resource_ids=(first_resource,),
                            sort="RESOURCE_START_ASC",
                            limit=500,
                        ),
                    )
                )
                deterministic_replay = runtime.presentation.comparison(request_id)
                after_counts = _counts(database)
                after_state = runtime.story_state()
            finally:
                database.close()

            observed_default_classes = {
                item.classification for item in comparison.operations
            }
            count_sum = sum(
                (
                    comparison_all.change_counts.added,
                    comparison_all.change_counts.changed,
                    comparison_all.change_counts.removed_by_fact,
                    comparison_all.change_counts.unchanged,
                )
            )
            schemas = presentation_contract_schemas()
            strict_schemas = all(
                schema.get("additionalProperties") is False
                for schema in schemas.values()
            )
            current_unchanged = (
                current is not None
                and current.schedule_version_id == base_version_id
                and current.content_fingerprint
                == plan_job.result["content_fingerprint"]
            )
            passed = (
                factory.counts.workshops == 3
                and factory.counts.resources == 24
                and base_page.page.unfiltered_total == 580
                and base_page.page.returned + base_tail.page.returned == 580
                and draft_page.page.unfiltered_total == 585
                and draft_page.page.returned + draft_tail.page.returned == 585
                and comparison.operation_universe_count == 585
                and comparison.change_counts.added == 5
                and comparison.change_counts.changed > 0
                and observed_default_classes == {"ADDED", "CHANGED"}
                and count_sum == 585
                and comparison_all.page.returned
                + comparison_tail.page.returned
                == 585
                and base_page.validation.status == "PASS"
                and draft_page.validation.status == "PASS"
                and base_page.boundary.publishable is False
                and draft_page.boundary.publishable is False
                and comparison.boundary.publishable is False
                and filtered.page.filtered_total < 585
                and all(
                    item.resource_id == first_resource
                    for item in filtered.assignments
                )
                and comparison.view_fingerprint
                == deterministic_replay.view_fingerprint
                and current_unchanged
                and before_counts == after_counts
                and before_state == after_state
                and strict_schemas
            )
            report: dict[str, Any] = {
                "runtime_evidence_version": REPORT_VERSION,
                "generated_at_utc": datetime.now(UTC)
                .replace(microsecond=0)
                .isoformat()
                .replace("+00:00", "Z"),
                "task_id": "TASK-DEMO-04",
                "task_family": "demo-exclusive",
                "status": "PASS" if passed else "FAIL",
                "profile": "showcase",
                "seed": 20260902,
                "run_id": run_id,
                "factory": {
                    "view_fingerprint": factory.view_fingerprint,
                    "workshops": factory.counts.workshops,
                    "resource_groups": factory.counts.resource_groups,
                    "resources": factory.counts.resources,
                    "maintenance_events": factory.counts.maintenance_events,
                    "unavailable_intervals": factory.counts.unavailable_intervals,
                    "timezone": factory.factory.timezone,
                },
                "base_schedule": {
                    "schedule_version_id": base_version_id,
                    "contract_version": base_page.version.contract_version,
                    "state": base_page.version.state,
                    "orders": len(base_page.orders),
                    "assignments": base_page.page.unfiltered_total,
                    "page_counts": [
                        base_page.page.returned,
                        base_tail.page.returned,
                    ],
                    "resources": len(base_page.resources),
                    "solver_status": base_page.solver.solver_status,
                    "validation_status": base_page.validation.status,
                    "view_fingerprint": base_page.view_fingerprint,
                },
                "draft_schedule": {
                    "schedule_version_id": draft_version_id,
                    "contract_version": draft_page.version.contract_version,
                    "state": draft_page.version.state,
                    "orders": len(draft_page.orders),
                    "assignments": draft_page.page.unfiltered_total,
                    "page_counts": [
                        draft_page.page.returned,
                        draft_tail.page.returned,
                    ],
                    "resources": len(draft_page.resources),
                    "solver_status": draft_page.solver.solver_status,
                    "validation_status": draft_page.validation.status,
                    "view_fingerprint": draft_page.view_fingerprint,
                },
                "comparison": {
                    "request_id": request_id,
                    "operation_universe_count": (
                        comparison.operation_universe_count
                    ),
                    "change_counts": comparison.change_counts.model_dump(
                        mode="json"
                    ),
                    "default_classifications": list(
                        comparison.query.classifications
                    ),
                    "default_observed_classifications": sorted(
                        observed_default_classes
                    ),
                    "all_page_counts": [
                        comparison_all.page.returned,
                        comparison_tail.page.returned,
                    ],
                    "affected_orders": len(comparison.affected_orders),
                    "stability": comparison.stability.model_dump(mode="json"),
                    "view_fingerprint": comparison.view_fingerprint,
                    "deterministic_replay": (
                        comparison.view_fingerprint
                        == deterministic_replay.view_fingerprint
                    ),
                },
                "filter_probe": {
                    "resource_id": first_resource,
                    "filtered_total": filtered.page.filtered_total,
                    "all_rows_match": all(
                        item.resource_id == first_resource
                        for item in filtered.assignments
                    ),
                },
                "payload_bytes": {
                    "factory": _json_bytes(factory.model_dump(mode="json")),
                    "base_first_500": _json_bytes(
                        base_page.model_dump(mode="json")
                    ),
                    "draft_first_500": _json_bytes(
                        draft_page.model_dump(mode="json")
                    ),
                    "comparison_default": _json_bytes(
                        comparison.model_dump(mode="json")
                    ),
                    "comparison_all_first_500": _json_bytes(
                        comparison_all.model_dump(mode="json")
                    ),
                },
                "presentation_seconds": {
                    "factory": factory_seconds,
                    "base_first_500": base_seconds,
                    "base_tail": base_tail_seconds,
                    "draft_first_500": draft_seconds,
                    "draft_tail": draft_tail_seconds,
                    "comparison_default": comparison_seconds,
                    "comparison_all_first_500": comparison_all_seconds,
                    "comparison_tail": comparison_tail_seconds,
                    "resource_filter": filtered_seconds,
                },
                "orchestration_seconds": {
                    "reset_accept": reset_seconds,
                    "reset_wait": reset_wait_seconds,
                    "plan_accept": plan_accept_seconds,
                    "plan_wait": plan_wait_seconds,
                    "urgent_accept": urgent_accept_seconds,
                    "urgent_wait": urgent_wait_seconds,
                },
                "read_only_invariant": {
                    "row_counts_before": before_counts,
                    "row_counts_after": after_counts,
                    "story_state_unchanged": before_state == after_state,
                    "current_publication_unchanged": current_unchanged,
                },
                "contracts": {
                    "schema_count": len(schemas),
                    "strict_root_additional_properties": strict_schemas,
                },
                "environment": {
                    "python": platform.python_version(),
                    "ortools": ortools.__version__,
                    "os": platform.platform(),
                    "cpu_count": os.cpu_count(),
                },
                "boundaries": {
                    "data_plane": "SIMULATION",
                    "production_authority": False,
                    "publishable": False,
                    "single_showcase_run_not_p95": True,
                    "browser_rendering_measured": False,
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
                "assignments": report["draft_schedule"]["assignments"],
                "changes": report["comparison"]["change_counts"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
