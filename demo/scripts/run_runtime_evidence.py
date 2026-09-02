"""Execute the TASK-DEMO-02 showcase runtime chain and write raw evidence."""

from __future__ import annotations

import argparse
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

from app.infrastructure.publication_repository import (  # noqa: E402
    SqlAlchemyPublicationRepository,
)
from app.infrastructure.workspace_persistence import WorkspaceDataPlane  # noqa: E402
from plantnexus_demo.composition import create_demo_runtime  # noqa: E402
from plantnexus_demo.persistence import RunDatabase, key_reference  # noqa: E402


REPORT_VERSION = "cnc-demo-runtime-evidence.v1"


def _fingerprint(document: dict[str, Any]) -> str:
    payload = json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return f"sha256:{sha256(payload).hexdigest()}"


def build_report() -> dict[str, Any]:
    with TemporaryDirectory(prefix="plantnexus-demo-02-") as temporary:
        runtime = create_demo_runtime(
            repository_root=REPOSITORY_ROOT,
            runtime_root=Path(temporary) / "runtime",
            auto_resume_queued=False,
        )
        try:
            started = perf_counter()
            reset = runtime.jobs.accept_reset(
                profile_name="showcase",
                idempotency_key="demo-02-evidence-reset-idempotency-0001",
                correlation_id="correlation-demo-02-evidence-reset",
            )
            reset_job = runtime.runner.wait(reset.job_id, timeout=60)
            reset_seconds = perf_counter() - started
            if reset_job.status != "SUCCEEDED" or reset_job.result is None:
                raise RuntimeError("showcase reset did not succeed")
            run_id = cast(str, reset_job.result["run_id"])
            reset_replay = runtime.jobs.accept_reset(
                profile_name="showcase",
                idempotency_key="demo-02-evidence-reset-idempotency-0001",
                correlation_id="correlation-demo-02-evidence-reset",
            )

            plan_started = perf_counter()
            plan = runtime.jobs.accept_initial_plan(
                expected_run_id=run_id,
                idempotency_key="demo-02-evidence-plan-idempotency-0001",
                correlation_id="correlation-demo-02-evidence-plan",
            )
            plan_job = runtime.runner.wait(plan.job_id, timeout=60)
            plan_seconds = perf_counter() - plan_started
            if plan_job.status != "SUCCEEDED" or plan_job.result is None:
                raise RuntimeError("showcase initial plan did not succeed")
            plan_replay = runtime.jobs.accept_initial_plan(
                expected_run_id=run_id,
                idempotency_key="demo-02-evidence-plan-idempotency-0001",
                correlation_id="correlation-demo-02-evidence-plan",
            )

            version_id = cast(str, plan_job.result["schedule_version_id"])
            content_fingerprint = cast(
                str, plan_job.result["content_fingerprint"]
            )
            activation_started = perf_counter()
            activation = runtime.baseline.execute(
                expected_run_id=run_id,
                schedule_version_id=version_id,
                content_fingerprint=content_fingerprint,
                expected_state_revision=cast(int, plan_job.result["state_revision"]),
                confirmation="ACTIVATE_SIMULATION_BASELINE",
                idempotency_key_reference=key_reference(
                    "demo-02-evidence-activation-idempotency-0001"
                ),
                correlation_id="correlation-demo-02-evidence-activation",
                occurred_at_utc="2026-09-02T10:00:00Z",
            )
            activation_seconds = perf_counter() - activation_started
            activation_replay = runtime.baseline.execute(
                expected_run_id=run_id,
                schedule_version_id=version_id,
                content_fingerprint=content_fingerprint,
                expected_state_revision=cast(int, plan_job.result["state_revision"]),
                confirmation="ACTIVATE_SIMULATION_BASELINE",
                idempotency_key_reference=key_reference(
                    "demo-02-evidence-activation-idempotency-0001"
                ),
                correlation_id="correlation-demo-02-evidence-activation",
                occurred_at_utc="2026-09-02T10:00:01Z",
            )

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
                manifest = database.get_manifest()
                current = SqlAlchemyPublicationRepository(
                    database.engine, data_plane=WorkspaceDataPlane.SIMULATION
                ).get_current(target="SIMULATION_INTERNAL")
                artifacts = database.list_artifacts()
                self_check = database.self_check()
            finally:
                database.close()
            state = runtime.story_state()
            passed = (
                manifest is not None
                and cast(dict[str, object], manifest["problem_counts"])[
                    "active_operations"
                ]
                == 580
                and plan_job.result["validation_status"] == "PASS"
                and plan_job.result["solver_status"] in {"OPTIMAL", "FEASIBLE"}
                and activation.state == "PUBLISHED"
                and current is not None
                and current.schedule_version_id == version_id
                and reset_replay.replayed
                and plan_replay.replayed
                and activation_replay.replayed
                and state["story_state"] == "BASELINE_PUBLISHED"
                and len(artifacts) == 7
            )
            report: dict[str, Any] = {
                "runtime_evidence_version": REPORT_VERSION,
                "generated_at_utc": datetime.now(UTC)
                .replace(microsecond=0)
                .isoformat()
                .replace("+00:00", "Z"),
                "task_id": "TASK-DEMO-02",
                "task_family": "demo-exclusive",
                "status": "PASS" if passed else "FAIL",
                "profile": "showcase",
                "run_id": run_id,
                "scenario_manifest": manifest,
                "jobs": {
                    "reset": {
                        "job_id": reset_job.job_id,
                        "status": reset_job.status,
                        "attempt": reset_job.attempt,
                        "stage_count": len(runtime.control.job_stages(reset_job.job_id)),
                        "exact_replay": reset_replay.replayed,
                    },
                    "initial_plan": {
                        "job_id": plan_job.job_id,
                        "status": plan_job.status,
                        "attempt": plan_job.attempt,
                        "stage_count": len(runtime.control.job_stages(plan_job.job_id)),
                        "exact_replay": plan_replay.replayed,
                    },
                },
                "initial_plan": plan_job.result,
                "activation": {
                    **activation.document,
                    "exact_replay": activation_replay.replayed,
                },
                "current_publication": (
                    None
                    if current is None
                    else {
                        "schedule_version_id": current.schedule_version_id,
                        "content_fingerprint": current.content_fingerprint,
                        "publication_id": current.publication_id,
                        "reference_revision": current.reference_revision,
                    }
                ),
                "story_state": state["story_state"],
                "artifacts": list(artifacts),
                "database_self_check": self_check,
                "timings": {
                    "reset_seconds": reset_seconds,
                    "initial_plan_seconds": plan_seconds,
                    "activation_seconds": activation_seconds,
                },
                "boundaries": {
                    "data_plane": "SIMULATION",
                    "production_authority": False,
                    "production_capacity_claim": "NOT_ESTABLISHED",
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
                "solver_status": report["initial_plan"]["solver_status"],
                "story_state": report["story_state"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
