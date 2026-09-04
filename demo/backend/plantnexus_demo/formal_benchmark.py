"""Formal, synthetic-only benchmark protocol for the CNC Demo.

The worker path deliberately executes the same durable orchestration used by the
Demo UI.  Aggregation is kept separate so every measured run can be isolated in
its own process and its process RSS can be sampled by the parent runner.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
import json
import math
from pathlib import Path
from time import perf_counter
from typing import Any, NoReturn, cast

from app.planning.contracts import contract_fingerprint
from app.infrastructure.publication_repository import SqlAlchemyPublicationRepository
from app.infrastructure.replan_repository import SqlAlchemyReplanLineageRepository
from app.infrastructure.schedule_version_repository import (
    SqlAlchemyScheduleVersionRepository,
)
from app.infrastructure.workspace_persistence import WorkspaceDataPlane

from .assets import DemoAssets, load_demo_assets
from .composition import DemoRuntime, create_demo_runtime
from .orchestration import DemoOperationError
from .persistence import RunDatabase, key_reference
from .presentation import ComparisonPresentationQuery, SchedulePresentationQuery
from .urgent import PriorityClass, UrgentOrderCommand


FORMAL_PROTOCOL_VERSION = "cnc-demo-formal-benchmark-protocol.v1"
FORMAL_SAMPLE_VERSION = "cnc-demo-formal-benchmark-sample.v1"
FORMAL_SUITE_VERSION = "cnc-demo-formal-benchmark-suite.v1"
SAMPLE_ROLES = ("preflight", "warmup", "measured")
PROFILE_NAMES = ("smoke", "showcase", "upper")


class FormalBenchmarkError(RuntimeError):
    """Stable benchmark contract failure."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class FormalProtocol:
    document: Mapping[str, object]
    fingerprint: str

    @property
    def baseline_version(self) -> str:
        return cast(str, self.document["baseline_version"])

    @property
    def measured_count(self) -> int:
        return cast(int, cast(Mapping[str, object], self.document["sample_plan"])["measured"])

    @property
    def urgent_fixture(self) -> Mapping[str, object]:
        return cast(Mapping[str, object], self.document["urgent_fixture"])


def _fail(code: str) -> NoReturn:
    raise FormalBenchmarkError(code)


def _exact(value: Mapping[str, object], expected: set[str], label: str) -> None:
    if set(value) != expected:
        _fail(f"INVALID_{label.upper()}_FIELDS")


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def fingerprint(value: object) -> str:
    return f"sha256:{sha256(_canonical_bytes(value)).hexdigest()}"


def _read_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise FormalBenchmarkError("PROTOCOL_READ_FAILED") from error
    if not isinstance(value, dict):
        _fail("PROTOCOL_NOT_OBJECT")
    return cast(dict[str, object], value)


def load_formal_protocol(
    demo_root: Path | None = None,
    *,
    assets: DemoAssets | None = None,
) -> FormalProtocol:
    root = Path(__file__).resolve().parents[2] if demo_root is None else demo_root.resolve()
    document = _read_json(root / "benchmarks" / "formal-protocol.v1.json")
    _exact(
        document,
        {
            "protocol_version",
            "baseline_version",
            "profile_set_version",
            "default_profile",
            "sample_plan",
            "profiles",
            "urgent_fixture",
            "showcase_thresholds",
            "boundaries",
        },
        "protocol",
    )
    if document["protocol_version"] != FORMAL_PROTOCOL_VERSION:
        _fail("UNSUPPORTED_PROTOCOL_VERSION")
    if document["baseline_version"] != "cnc-demo-formal-benchmark-baseline.v1":
        _fail("UNSUPPORTED_BASELINE_VERSION")
    if document["profile_set_version"] != "cnc-demo-benchmark-profiles.v2":
        _fail("PROFILE_SET_VERSION_MISMATCH")
    if document["default_profile"] != "showcase":
        _fail("DEFAULT_PROFILE_MISMATCH")

    sample_plan = cast(Mapping[str, object], document.get("sample_plan"))
    _exact(sample_plan, {"preflight", "warmup", "measured", "percentile_method"}, "sample_plan")
    if sample_plan != {
        "preflight": 1,
        "warmup": 1,
        "measured": 5,
        "percentile_method": "nearest-rank",
    }:
        _fail("SAMPLE_PLAN_MISMATCH")

    loaded_assets = load_demo_assets() if assets is None else assets
    profile_document = _read_json(root / "benchmarks" / "profiles.json")
    if profile_document.get("benchmark_profile_set_version") != document["profile_set_version"]:
        _fail("PROFILE_SET_SOURCE_MISMATCH")
    protocol_profiles = cast(Mapping[str, object], document.get("profiles"))
    if tuple(sorted(protocol_profiles)) != tuple(sorted(PROFILE_NAMES)):
        _fail("PROFILE_SET_MISMATCH")
    for name in PROFILE_NAMES:
        declared = cast(Mapping[str, object], protocol_profiles[name])
        _exact(
            declared,
            {"profile_id", "initial_solve_seconds", "replan_solve_seconds"},
            f"profile_{name}",
        )
        profile = loaded_assets.profile(name)
        if declared != {
            "profile_id": profile.profile_id,
            "initial_solve_seconds": profile.initial_solve_seconds,
            "replan_solve_seconds": profile.replan_solve_seconds,
        }:
            _fail(f"PROFILE_{name.upper()}_LIMIT_MISMATCH")

    fixture = cast(Mapping[str, object], document.get("urgent_fixture"))
    _exact(
        fixture,
        {
            "fixture_id",
            "fixture_version",
            "route_template_id",
            "quantity",
            "due_at_local",
            "timezone",
            "priority_class",
            "note",
        },
        "urgent_fixture",
    )
    if (
        fixture.get("fixture_id") != "CNC-DEMO-URGENT-FIXTURE-001"
        or fixture.get("fixture_version") != "1.0.0"
        or fixture.get("route_template_id") != "CNC-ROUTE-5"
        or fixture.get("quantity") != 5
        or fixture.get("due_at_local") != "2026-09-09T18:00:00"
        or fixture.get("timezone") != "Asia/Shanghai"
        or fixture.get("priority_class") != "URGENT"
        or not isinstance(fixture.get("note"), str)
    ):
        _fail("URGENT_FIXTURE_MISMATCH")

    thresholds = cast(Mapping[str, object], document.get("showcase_thresholds"))
    _exact(
        thresholds,
        {
            "initial_end_to_end_p95_seconds_max",
            "urgent_replan_end_to_end_p95_seconds_max",
            "non_solving_stages_p95_seconds_max",
            "presentation_api_p95_seconds_max",
            "job_state_api_p95_seconds_max",
            "backend_peak_rss_p95_bytes_max",
            "validator_and_change_report_required_passes",
        },
        "showcase_thresholds",
    )
    boundaries = cast(Mapping[str, object], document.get("boundaries"))
    _exact(
        boundaries,
        {
            "data_plane",
            "synthetic_only",
            "production_capacity_claim",
            "production_sla_claim",
            "first_feasible_metric",
        },
        "boundaries",
    )
    if boundaries != {
        "data_plane": "SIMULATION_ONLY",
        "synthetic_only": True,
        "production_capacity_claim": "NOT_ESTABLISHED",
        "production_sla_claim": "NOT_ESTABLISHED",
        "first_feasible_metric": "NOT_REPORTED_NO_RELIABLE_CALLBACK",
    }:
        _fail("PROTOCOL_BOUNDARY_MISMATCH")
    return FormalProtocol(document=document, fingerprint=fingerprint(document))


def nearest_rank(values: Sequence[float | int], percentile: float) -> float:
    if not values or not 0 < percentile <= 1:
        raise ValueError("nearest-rank requires values and percentile in (0, 1]")
    ordered = sorted(float(value) for value in values)
    rank = max(1, math.ceil(percentile * len(ordered)))
    return ordered[rank - 1]


def distribution(values: Sequence[float | int]) -> dict[str, object]:
    if not values:
        raise ValueError("distribution requires at least one sample")
    raw = [float(value) for value in values]
    ordered = sorted(raw)
    count = len(ordered)
    midpoint = count // 2
    median = (
        ordered[midpoint]
        if count % 2 == 1
        else (ordered[midpoint - 1] + ordered[midpoint]) / 2
    )
    return {
        "raw": raw,
        "count": count,
        "p50": median,
        "p95": nearest_rank(raw, 0.95),
        "max": ordered[-1],
        "percentile_method": "nearest-rank",
    }


def _time(call: Any) -> tuple[Any, float]:
    started = perf_counter()
    value = call()
    return value, perf_counter() - started


def _job_stage_seconds(runtime: DemoRuntime, job_id: str) -> dict[str, float]:
    stages = runtime.control.job_stages(job_id)
    values: dict[str, float] = {}
    for stage in stages:
        name = stage.get("stage")
        elapsed = stage.get("elapsed_seconds")
        if stage.get("status") != "SUCCEEDED" or not isinstance(name, str) or not isinstance(
            elapsed, (float, int)
        ):
            _fail("INCOMPLETE_JOB_STAGE")
        if name in values:
            _fail("DUPLICATE_JOB_STAGE")
        values[name] = float(elapsed)
    return values


def _artifact(
    database: RunDatabase,
    *,
    kind: str,
    reference: Mapping[str, object],
) -> dict[str, object]:
    artifact_id = reference.get("artifact_id")
    expected = reference.get("fingerprint")
    if not isinstance(artifact_id, str) or not isinstance(expected, str):
        _fail("INVALID_ARTIFACT_REFERENCE")
    document = database.get_artifact(artifact_kind=kind, artifact_id=artifact_id)
    observed = None
    if document is not None:
        if kind == "SNAPSHOT":
            observed = document.get("snapshot_hash")
        elif kind == "PLANNING_PROBLEM":
            observed = document.get("problem_hash")
        else:
            observed = contract_fingerprint(document)
    if document is None or observed != expected:
        _fail("ARTIFACT_REFERENCE_MISMATCH")
    return document


def _solver_summary(
    report: Mapping[str, object],
    *,
    assignment_count: int,
    candidate_fingerprint: str,
) -> dict[str, object]:
    timings = cast(Mapping[str, object], report.get("timings"))
    stages = cast(Sequence[Mapping[str, object]], report.get("objective_stage_results"))
    model = cast(Mapping[str, object], report.get("model_metrics"))
    status = report.get("solver_status")
    if status not in {"OPTIMAL", "FEASIBLE"} or not stages:
        _fail("SOLVER_NO_VALIDATED_CANDIDATE")
    first_stage = stages[0]
    return {
        "solver_status": status,
        "planning_run_outcome": report.get("planning_run_outcome", "COMPLETED"),
        "assignment_count": assignment_count,
        "candidate_fingerprint": candidate_fingerprint,
        "objective_value": first_stage.get("objective_value"),
        "best_bound": first_stage.get("best_bound"),
        "relative_gap": first_stage.get("relative_gap"),
        "limits": report.get("limits"),
        "model_metrics": {
            "variables": model.get("variables"),
            "constraints": model.get("constraints"),
            "optional_intervals": model.get("optional_intervals"),
        },
        "timings": {
            "model_build_seconds": timings.get("model_build_seconds"),
            "solve_seconds": timings.get("solve_seconds"),
            "validation_seconds": timings.get("validation_seconds"),
            "total_seconds": timings.get("total_seconds"),
            "first_feasible_seconds": None,
            "first_feasible_status": "NOT_REPORTED_NO_RELIABLE_CALLBACK",
        },
        "memory_peak_mb_solver_telemetry": report.get("memory_peak_mb"),
        "objective_stage_results": [dict(stage) for stage in stages],
    }


def _json_bytes(value: object) -> int:
    return len(_canonical_bytes(value))


def _database_sizes(database: RunDatabase) -> tuple[int, int]:
    paths = (
        database.database_path,
        Path(str(database.database_path) + "-wal"),
        Path(str(database.database_path) + "-shm"),
    )
    database_bytes = sum(path.stat().st_size for path in paths if path.exists())
    with database.engine.connect() as connection:
        artifact_bytes = int(
            connection.exec_driver_sql(
                "SELECT COALESCE(SUM(length(canonical_json)), 0) FROM demo_artifacts"
            ).scalar_one()
        )
    return database_bytes, artifact_bytes


def _completed_fingerprint(snapshot: Mapping[str, object]) -> tuple[int, str]:
    operations = cast(Sequence[Mapping[str, object]], snapshot["operation_instances"])
    completed = [dict(item) for item in operations if item.get("status") == "COMPLETED"]
    completed.sort(key=lambda item: cast(str, item["operation_instance_id"]))
    return len(completed), fingerprint(completed)


def _presentation_measurements(
    runtime: DemoRuntime,
    *,
    manifest: Mapping[str, object],
    base_version_id: str,
    draft_version_id: str,
    request_id: str,
) -> dict[str, object]:
    horizon_start = datetime.fromisoformat(
        cast(str, manifest["horizon_start_utc"]).replace("Z", "+00:00")
    )
    start = horizon_start - timedelta(hours=6)
    end = min(
        datetime.fromisoformat(cast(str, manifest["horizon_end_utc"]).replace("Z", "+00:00")),
        start + timedelta(hours=72),
    )
    query = SchedulePresentationQuery(
        start_at_utc=start.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        end_at_utc=end.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        sort="ORDER_START_ASC",
        limit=160,
    )
    factory, factory_seconds = _time(runtime.presentation.factory)
    base, base_seconds = _time(lambda: runtime.presentation.schedule(base_version_id, query))
    draft, draft_seconds = _time(lambda: runtime.presentation.schedule(draft_version_id, query))
    comparison, comparison_seconds = _time(
        lambda: runtime.presentation.comparison(
            request_id,
            ComparisonPresentationQuery(limit=120),
        )
    )
    timings = {
        "factory": factory_seconds,
        "base_schedule": base_seconds,
        "draft_schedule": draft_seconds,
        "comparison": comparison_seconds,
    }
    payloads = {
        "factory": _json_bytes(factory.model_dump(mode="json")),
        "base_schedule": _json_bytes(base.model_dump(mode="json")),
        "draft_schedule": _json_bytes(draft.model_dump(mode="json")),
        "comparison": _json_bytes(comparison.model_dump(mode="json")),
    }
    return {
        "api_seconds": timings,
        "max_api_seconds": max(timings.values()),
        "payload_bytes": payloads,
        "factory_counts": factory.counts.model_dump(mode="json"),
        "base_returned_assignments": base.page.returned,
        "base_unfiltered_assignments": base.page.unfiltered_total,
        "draft_returned_assignments": draft.page.returned,
        "draft_unfiltered_assignments": draft.page.unfiltered_total,
        "comparison_returned_operations": comparison.page.returned,
        "comparison_operation_universe": comparison.operation_universe_count,
        "comparison_validation": "PASS",
        "read_only": True,
    }


def run_formal_sample(
    *,
    repository_root: Path,
    runtime_root: Path,
    profile_name: str,
    role: str,
    sequence: int,
) -> dict[str, object]:
    if profile_name not in PROFILE_NAMES or role not in SAMPLE_ROLES or sequence < 1:
        _fail("INVALID_SAMPLE_IDENTITY")
    protocol = load_formal_protocol(repository_root / "demo")
    profile = load_demo_assets().profile(profile_name)
    sample_id = f"{profile_name}-{role}-{sequence:02d}"
    runtime = create_demo_runtime(
        repository_root=repository_root,
        runtime_root=runtime_root,
        auto_resume_queued=False,
    )
    overall_started = perf_counter()
    try:
        reset, reset_accept_seconds = _time(
            lambda: runtime.jobs.accept_reset(
                profile_name=profile_name,
                idempotency_key=f"demo-09-{sample_id}-reset",
                correlation_id=f"correlation-demo-09-{sample_id}-reset",
            )
        )
        reset_job, reset_wait_seconds = _time(
            lambda: runtime.runner.wait(reset.job_id, timeout=180.0)
        )
        if reset_job.status != "SUCCEEDED" or reset_job.result is None:
            _fail("RESET_JOB_FAILED")
        run_id = cast(str, reset_job.result["run_id"])
        reset_stages = _job_stage_seconds(runtime, reset.job_id)

        plan, plan_accept_seconds = _time(
            lambda: runtime.jobs.accept_initial_plan(
                expected_run_id=run_id,
                idempotency_key=f"demo-09-{sample_id}-initial",
                correlation_id=f"correlation-demo-09-{sample_id}-initial",
            )
        )
        plan_job, plan_wait_seconds = _time(
            lambda: runtime.runner.wait(
                plan.job_id,
                timeout=float(profile.initial_solve_seconds) + 180.0,
            )
        )
        if plan_job.status != "SUCCEEDED" or plan_job.result is None:
            _fail("INITIAL_PLAN_JOB_FAILED")
        plan_stages = _job_stage_seconds(runtime, plan.job_id)
        base_version_id = cast(str, plan_job.result["schedule_version_id"])

        activation, activation_seconds = _time(
            lambda: runtime.baseline.execute(
                expected_run_id=run_id,
                schedule_version_id=base_version_id,
                content_fingerprint=cast(str, plan_job.result["content_fingerprint"]),
                expected_state_revision=cast(int, plan_job.result["state_revision"]),
                confirmation="ACTIVATE_SIMULATION_BASELINE",
                idempotency_key_reference=key_reference(
                    f"demo-09-{sample_id}-activate"
                ),
                correlation_id=f"correlation-demo-09-{sample_id}-activate",
                occurred_at_utc="2026-09-04T08:00:00Z",
            )
        )
        if activation.state != "PUBLISHED":
            _fail("BASELINE_ACTIVATION_FAILED")

        active = runtime.control.active_run()
        if active is None or active.run_id != run_id:
            _fail("ACTIVE_RUN_MISMATCH")
        database = RunDatabase(
            repository_root=repository_root,
            database_path=runtime.paths.resolve_relative_database(
                active.database_relative_path
            ),
        )
        try:
            manifest = database.get_manifest()
            if manifest is None:
                _fail("SCENARIO_MANIFEST_MISSING")
            schedules = SqlAlchemyScheduleVersionRepository(
                database.engine, data_plane=WorkspaceDataPlane.SIMULATION
            )
            publications = SqlAlchemyPublicationRepository(
                database.engine, data_plane=WorkspaceDataPlane.SIMULATION
            )
            base_schedule = schedules.get(base_version_id)
            current_before = publications.get_current(target="SIMULATION_INTERNAL")
            if base_schedule is None or current_before is None:
                _fail("BASELINE_LINEAGE_MISSING")
            base_lineage = cast(Mapping[str, object], base_schedule["lineage"])
            initial_solver_report = _artifact(
                database,
                kind="SOLVER_REPORT",
                reference=cast(Mapping[str, object], base_lineage["solver_report"]),
            )
            initial_validation = _artifact(
                database,
                kind="VALIDATION_REPORT",
                reference=cast(Mapping[str, object], base_lineage["validation_report"]),
            )
            initial_snapshot = _artifact(
                database,
                kind="SNAPSHOT",
                reference=cast(Mapping[str, object], base_lineage["snapshot"]),
            )
            initial_assignments = cast(
                Sequence[Mapping[str, object]],
                cast(Mapping[str, object], base_schedule["content"])["assignments"],
            )
            initial_solver = _solver_summary(
                initial_solver_report,
                assignment_count=len(initial_assignments),
                candidate_fingerprint=cast(
                    str,
                    cast(Mapping[str, object], base_lineage["planning_solution"])[
                        "fingerprint"
                    ],
                ),
            )
            if (
                initial_validation.get("status") != "PASS"
                or initial_validation.get("hard_violation_count") != 0
            ):
                _fail("INITIAL_VALIDATOR_FAILED")
        finally:
            database.close()

        fixture = protocol.urgent_fixture
        urgent_command = UrgentOrderCommand(
            command_version="cnc-demo-urgent-order-command.v1",
            expected_run_id=run_id,
            expected_base_version_id=base_version_id,
            route_template_id=cast(str, fixture["route_template_id"]),
            quantity=cast(int, fixture["quantity"]),
            due_at_local=cast(str, fixture["due_at_local"]),
            priority_class=cast(PriorityClass, fixture["priority_class"]),
            note=cast(str, fixture["note"]),
        )
        urgent, urgent_accept_seconds = _time(
            lambda: runtime.jobs.accept_urgent_order(
                command=urgent_command,
                idempotency_key=f"demo-09-{sample_id}-urgent",
                correlation_id=f"correlation-demo-09-{sample_id}-urgent",
            )
        )
        urgent_job, urgent_wait_seconds = _time(
            lambda: runtime.runner.wait(
                urgent.job_id,
                timeout=float(profile.replan_solve_seconds) + 240.0,
            )
        )
        if urgent_job.status != "SUCCEEDED" or urgent_job.result is None:
            _fail("URGENT_REPLAN_JOB_FAILED")
        urgent_stages = _job_stage_seconds(runtime, urgent.job_id)
        draft_version_id = cast(str, urgent_job.result["schedule_version_id"])
        request_id = cast(str, urgent_job.result["request_id"])
        attempt_id = cast(str, urgent_job.result["attempt_id"])

        database = RunDatabase(
            repository_root=repository_root,
            database_path=runtime.paths.resolve_relative_database(
                cast(str, runtime.control.active_run().database_relative_path)  # type: ignore[union-attr]
            ),
        )
        try:
            schedules = SqlAlchemyScheduleVersionRepository(
                database.engine, data_plane=WorkspaceDataPlane.SIMULATION
            )
            publications = SqlAlchemyPublicationRepository(
                database.engine, data_plane=WorkspaceDataPlane.SIMULATION
            )
            draft = schedules.get(draft_version_id)
            current_after = publications.get_current(target="SIMULATION_INTERNAL")
            stored = SqlAlchemyReplanLineageRepository(
                database.engine, data_plane=WorkspaceDataPlane.SIMULATION
            ).get_applied_result_for_attempt(attempt_id)
            if draft is None or stored is None or current_after is None:
                _fail("REPLAN_LINEAGE_MISSING")
            draft_content = cast(Mapping[str, object], draft["content"])
            draft_assignments = cast(
                Sequence[Mapping[str, object]], draft_content["assignments"]
            )
            candidate = cast(Mapping[str, object], stored.solver_report["candidate"])
            replan_solver = _solver_summary(
                stored.solver_report,
                assignment_count=len(draft_assignments),
                candidate_fingerprint=cast(str, candidate["candidate_fingerprint"]),
            )
            if (
                stored.validation_report.get("status") != "PASS"
                or stored.validation_report.get("hard_violation_count") != 0
            ):
                _fail("REPLAN_VALIDATOR_FAILED")
            change_report = stored.change_report
            classifications = Counter(
                cast(str, operation["classification"])
                for operation in cast(
                    Sequence[Mapping[str, object]], change_report["operations"]
                )
            )
            stability = cast(Mapping[str, object], change_report["stability"])
            fact_locks = cast(
                Mapping[str, object], stored.validation_report["fact_lock_evidence"]
            )
            draft_lineage = cast(Mapping[str, object], draft["lineage"])
            new_snapshot = _artifact(
                database,
                kind="SNAPSHOT",
                reference=cast(Mapping[str, object], draft_lineage["new_snapshot"]),
            )
            completed_before = _completed_fingerprint(initial_snapshot)
            completed_after = _completed_fingerprint(new_snapshot)
            database_bytes, artifact_bytes = _database_sizes(database)
            self_check = database.self_check()
            publication_unchanged = (
                current_after.schedule_version_id == base_version_id
                and current_after.content_fingerprint
                == cast(str, base_schedule["content_fingerprint"])
            )
        finally:
            database.close()

        presentation = _presentation_measurements(
            runtime,
            manifest=manifest,
            base_version_id=base_version_id,
            draft_version_id=draft_version_id,
            request_id=request_id,
        )
        _, state_api_seconds = _time(runtime.story_state)
        _, job_api_seconds = _time(lambda: runtime.control.get_job(urgent.job_id))

        before_failure_run = runtime.active_run_id()
        failure_started = perf_counter()
        failure_code: str | None = None
        try:
            runtime.runner.reset.execute(
                run_id=(
                    "run-demo09-failure-"
                    + sha256(sample_id.encode("utf-8")).hexdigest()[:24]
                ),
                profile_name=profile_name,
                expected_active_run_id=before_failure_run,
                created_at_utc="2026-09-04T09:00:00Z",
                fault_point="BEFORE_SWITCH",
            )
        except DemoOperationError as error:
            failure_code = error.code
        failure_seconds = perf_counter() - failure_started
        failure_preserved_active = runtime.active_run_id() == before_failure_run

        initial_non_solving = sum(
            elapsed for name, elapsed in plan_stages.items() if name != "SOLVING"
        )
        urgent_non_solving = sum(
            elapsed for name, elapsed in urgent_stages.items() if name != "SOLVING"
        )
        movement_condition = (
            classifications["CHANGED"] > 0
            if profile_name == "showcase"
            else classifications["UNCHANGED"] > 0
        )
        b4_valid = (
            classifications["ADDED"] == 5
            and movement_condition
            and classifications["UNCHANGED"] > 0
            and sum(classifications.values())
            == cast(int, change_report["operation_universe_count"])
            and completed_before == completed_after
            and cast(int, fact_locks["running_fact_count"]) == profile.running_operation_count
            and cast(int, fact_locks["explicit_hard_lock_count"]) == profile.hard_lock_count
            and cast(int, fact_locks["freeze_derived_hard_lock_count"]) > 0
            and publication_unchanged
        )
        assertions = {
            "profile_and_seed_match": (
                manifest["scenario_id"] == profile.profile_id
                and manifest["seed"] == profile.seed
            ),
            "source_counts_match": (
                cast(Mapping[str, object], manifest["source_counts"])["demand_orders"]
                == profile.order_count
                and cast(Mapping[str, object], manifest["source_counts"])[
                    "routing_operations"
                ]
                == profile.operation_count
                and cast(Mapping[str, object], manifest["source_counts"])["resources"]
                == profile.resource_count
            ),
            "solve_limits_match_frozen_profile": (
                manifest["initial_solve_seconds"] == profile.initial_solve_seconds
                and manifest["replan_solve_seconds"] == profile.replan_solve_seconds
            ),
            "initial_candidate_validator_pass": (
                plan_job.result["solver_status"] in {"OPTIMAL", "FEASIBLE"}
                and plan_job.result["validation_status"] == "PASS"
            ),
            "baseline_published": activation.state == "PUBLISHED",
            "replan_candidate_validator_pass": (
                urgent_job.result["solver_status"] in {"OPTIMAL", "FEASIBLE"}
                and urgent_job.result["validation_status"] == "PASS"
            ),
            "change_report_and_preservation_pass": b4_valid,
            "presentation_contract_pass": (
                presentation["comparison_validation"] == "PASS"
                and presentation["read_only"] is True
            ),
            "reset_failure_preserves_active": (
                failure_code == "RESET_FAILED" and failure_preserved_active
            ),
            "database_self_check_pass": self_check.get("status") == "PASS",
        }
        passed = all(assertions.values())
        report: dict[str, object] = {
            "sample_version": FORMAL_SAMPLE_VERSION,
            "sample_id": sample_id,
            "role": role,
            "sequence": sequence,
            "generated_at_utc": datetime.now(UTC)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z"),
            "status": "PASS" if passed else "FAIL",
            "protocol": {
                "version": FORMAL_PROTOCOL_VERSION,
                "fingerprint": protocol.fingerprint,
                "baseline_version": protocol.baseline_version,
            },
            "profile": {
                "name": profile_name,
                "profile_id": profile.profile_id,
                "scenario_version": profile.scenario_version,
                "seed": profile.seed,
                "orders": profile.order_count,
                "operations": profile.operation_count,
                "active_operations": profile.active_operation_count,
                "resources": profile.resource_count,
                "horizon_days": profile.horizon_days,
                "initial_solve_seconds": profile.initial_solve_seconds,
                "replan_solve_seconds": profile.replan_solve_seconds,
            },
            "b1_data_import": {
                "end_to_end_seconds": reset_accept_seconds + reset_wait_seconds,
                "stage_seconds": reset_stages,
                "dataset_hash": manifest["dataset_hash"],
                "snapshot_hash": manifest["snapshot_hash"],
                "problem_hash": manifest["problem_hash"],
                "batch_request_fingerprint": manifest["batch_request_fingerprint"],
                "assets_digest": manifest["assets_digest"],
                "source_counts": manifest["source_counts"],
                "problem_counts": manifest["problem_counts"],
                "quality_status": "PASS",
            },
            "b2_initial_plan": {
                "end_to_end_seconds": plan_accept_seconds + plan_wait_seconds,
                "stage_seconds": plan_stages,
                "non_solving_stages_seconds": initial_non_solving,
                "solver": initial_solver,
                "validator": {
                    "status": initial_validation["status"],
                    "hard_violation_count": initial_validation[
                        "hard_violation_count"
                    ],
                    "independent": True,
                },
                "schedule_state": plan_job.result["schedule_state"],
            },
            "b3_baseline_activation": {
                "end_to_end_seconds": activation_seconds,
                "state": activation.state,
                "current_publication_read_back": True,
            },
            "b4_urgent_replan": {
                "fixture_id": fixture["fixture_id"],
                "fixture_version": fixture["fixture_version"],
                "fixture_fingerprint": fingerprint(fixture),
                "end_to_end_seconds": urgent_accept_seconds + urgent_wait_seconds,
                "stage_seconds": urgent_stages,
                "non_solving_stages_seconds": urgent_non_solving,
                "solver": replan_solver,
                "validator": {
                    "status": stored.validation_report["status"],
                    "hard_violation_count": stored.validation_report[
                        "hard_violation_count"
                    ],
                    "independent": True,
                },
                "change_report": {
                    "status": "PASS",
                    "fingerprint": change_report["report_fingerprint"],
                    "operation_universe_count": change_report[
                        "operation_universe_count"
                    ],
                    "classifications": {
                        name: classifications[name]
                        for name in (
                            "ADDED",
                            "CHANGED",
                            "UNCHANGED",
                            "REMOVED_BY_FACT",
                        )
                    },
                    "stability": dict(stability),
                },
                "preservation": {
                    "completed_before": completed_before[0],
                    "completed_after": completed_after[0],
                    "completed_fingerprint_unchanged": completed_before == completed_after,
                    "running_fact_count": fact_locks["running_fact_count"],
                    "explicit_hard_lock_count": fact_locks[
                        "explicit_hard_lock_count"
                    ],
                    "freeze_derived_hard_lock_count": fact_locks[
                        "freeze_derived_hard_lock_count"
                    ],
                    "current_publication_unchanged": publication_unchanged,
                },
                "schedule_state": urgent_job.result["schedule_state"],
            },
            "b5_presentation": {
                **presentation,
                "job_api_seconds": job_api_seconds,
                "state_api_seconds": state_api_seconds,
                "max_job_state_api_seconds": max(
                    job_api_seconds, state_api_seconds
                ),
                "browser_first_screen": "MEASURED_BY_SEPARATE_PLAYWRIGHT_SUITE",
            },
            "b6_reset_recovery": {
                "failure_probe_seconds": failure_seconds,
                "fault_point": "BEFORE_SWITCH",
                "error_code": failure_code,
                "old_active_run_preserved": failure_preserved_active,
            },
            "resources": {
                "backend_peak_rss_bytes": None,
                "backend_peak_rss_method": "PARENT_PROCESS_SAMPLER_PENDING",
                "sqlite_database_bytes": database_bytes,
                "artifact_canonical_json_bytes": artifact_bytes,
            },
            "overall_wall_seconds": perf_counter() - overall_started,
            "assertions": assertions,
            "boundaries": dict(
                cast(Mapping[str, object], protocol.document["boundaries"])
            )
            | {
                "runtime_path_recorded": False,
                "session_token_recorded": False,
                "p7_registration": None,
            },
        }
        report["sample_fingerprint"] = fingerprint(report)
        return report
    finally:
        runtime.close()


def attach_rss_measurement(
    report: Mapping[str, object],
    *,
    peak_rss_bytes: int,
    samples: int,
    interval_seconds: float,
    method: str,
) -> dict[str, object]:
    value = json.loads(json.dumps(report, ensure_ascii=False))
    if not isinstance(value, dict) or value.get("sample_version") != FORMAL_SAMPLE_VERSION:
        _fail("INVALID_SAMPLE_FOR_RSS")
    resources = value.get("resources")
    if not isinstance(resources, dict):
        _fail("INVALID_SAMPLE_RESOURCES")
    resources["backend_peak_rss_bytes"] = peak_rss_bytes
    resources["backend_peak_rss_method"] = method
    resources["rss_sample_count"] = samples
    resources["rss_sampling_interval_seconds"] = interval_seconds
    value.pop("sample_fingerprint", None)
    value["sample_fingerprint"] = fingerprint(value)
    return cast(dict[str, object], value)


def _path_value(sample: Mapping[str, object], path: str) -> float:
    value: object = sample
    for part in path.split("."):
        if not isinstance(value, Mapping) or part not in value:
            raise ValueError(f"missing metric path: {path}")
        value = value[part]
    if not isinstance(value, (float, int)) or isinstance(value, bool):
        raise ValueError(f"metric is not numeric: {path}")
    return float(value)


def summarize_profile(
    profile_name: str,
    samples: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    measured = [sample for sample in samples if sample.get("role") == "measured"]
    roles = Counter(cast(str, sample.get("role")) for sample in samples)
    sample_plan_ok = roles == Counter({"preflight": 1, "warmup": 1, "measured": 5})
    all_pass = all(sample.get("status") == "PASS" for sample in samples)
    if not measured:
        return {
            "profile": profile_name,
            "status": "FAIL",
            "sample_plan": dict(roles),
            "sample_plan_pass": sample_plan_ok,
            "error": "NO_MEASURED_SAMPLES",
        }
    metric_paths = {
        "data_import_end_to_end_seconds": "b1_data_import.end_to_end_seconds",
        "initial_end_to_end_seconds": "b2_initial_plan.end_to_end_seconds",
        "initial_solver_seconds": "b2_initial_plan.solver.timings.solve_seconds",
        "initial_validation_seconds": "b2_initial_plan.solver.timings.validation_seconds",
        "initial_non_solving_stages_seconds": "b2_initial_plan.non_solving_stages_seconds",
        "activation_end_to_end_seconds": "b3_baseline_activation.end_to_end_seconds",
        "urgent_replan_end_to_end_seconds": "b4_urgent_replan.end_to_end_seconds",
        "urgent_replan_solver_seconds": "b4_urgent_replan.solver.timings.solve_seconds",
        "urgent_replan_validation_seconds": "b4_urgent_replan.solver.timings.validation_seconds",
        "urgent_replan_non_solving_stages_seconds": "b4_urgent_replan.non_solving_stages_seconds",
        "presentation_api_max_seconds": "b5_presentation.max_api_seconds",
        "job_state_api_max_seconds": "b5_presentation.max_job_state_api_seconds",
        "reset_failure_probe_seconds": "b6_reset_recovery.failure_probe_seconds",
        "backend_peak_rss_bytes": "resources.backend_peak_rss_bytes",
        "sqlite_database_bytes": "resources.sqlite_database_bytes",
        "artifact_canonical_json_bytes": "resources.artifact_canonical_json_bytes",
        "overall_wall_seconds": "overall_wall_seconds",
    }
    distributions = {
        name: distribution([_path_value(sample, path) for sample in measured])
        for name, path in metric_paths.items()
    }
    initial_statuses = Counter(
        cast(
            str,
            cast(Mapping[str, object], cast(Mapping[str, object], sample["b2_initial_plan"])["solver"])[
                "solver_status"
            ],
        )
        for sample in measured
    )
    replan_statuses = Counter(
        cast(
            str,
            cast(Mapping[str, object], cast(Mapping[str, object], sample["b4_urgent_replan"])["solver"])[
                "solver_status"
            ],
        )
        for sample in measured
    )
    hashes = {
        name: sorted(
            {
                cast(str, cast(Mapping[str, object], sample["b1_data_import"])[name])
                for sample in measured
            }
        )
        for name in ("dataset_hash", "snapshot_hash", "problem_hash", "assets_digest")
    }
    initial_fingerprints = sorted(
        {
            cast(
                str,
                cast(Mapping[str, object], cast(Mapping[str, object], sample["b2_initial_plan"])["solver"])[
                    "candidate_fingerprint"
                ],
            )
            for sample in measured
        }
    )
    replan_fingerprints = sorted(
        {
            cast(
                str,
                cast(Mapping[str, object], cast(Mapping[str, object], sample["b4_urgent_replan"])["solver"])[
                    "candidate_fingerprint"
                ],
            )
            for sample in measured
        }
    )
    gates = {
        "sample_plan": sample_plan_ok,
        "all_samples_pass": all_pass,
        "measured_initial_status_and_validator_5_of_5": all(
            cast(Mapping[str, object], sample["assertions"])[
                "initial_candidate_validator_pass"
            ]
            is True
            for sample in measured
        ),
        "measured_replan_status_validator_change_report_5_of_5": all(
            cast(Mapping[str, object], sample["assertions"])[
                "replan_candidate_validator_pass"
            ]
            is True
            and cast(Mapping[str, object], sample["assertions"])[
                "change_report_and_preservation_pass"
            ]
            is True
            for sample in measured
        ),
        "measured_presentation_5_of_5": all(
            cast(Mapping[str, object], sample["assertions"])[
                "presentation_contract_pass"
            ]
            is True
            for sample in measured
        ),
        "measured_reset_recovery_5_of_5": all(
            cast(Mapping[str, object], sample["assertions"])[
                "reset_failure_preserves_active"
            ]
            is True
            for sample in measured
        ),
        "deterministic_inputs": all(len(values) == 1 for values in hashes.values()),
    }
    return {
        "profile": profile_name,
        "status": "PASS" if all(gates.values()) else "FAIL",
        "sample_plan": dict(roles),
        "sample_plan_pass": sample_plan_ok,
        "measured_sample_ids": [cast(str, sample["sample_id"]) for sample in measured],
        "distributions": distributions,
        "solver_status_distributions": {
            "initial": dict(sorted(initial_statuses.items())),
            "urgent_replan": dict(sorted(replan_statuses.items())),
        },
        "determinism": {
            "input_fingerprints": hashes,
            "initial_candidate_fingerprints": initial_fingerprints,
            "urgent_replan_candidate_fingerprints": replan_fingerprints,
            "rule": "OPTIMAL must be identical; time-bounded FEASIBLE may vary and is reported.",
        },
        "gates": gates,
    }


def showcase_thresholds(
    summary: Mapping[str, object], protocol: FormalProtocol
) -> dict[str, object]:
    distributions = cast(Mapping[str, Mapping[str, object]], summary["distributions"])
    thresholds = cast(
        Mapping[str, object], protocol.document["showcase_thresholds"]
    )
    non_solving = max(
        cast(float, distributions["initial_non_solving_stages_seconds"]["p95"]),
        cast(float, distributions["urgent_replan_non_solving_stages_seconds"]["p95"]),
    )
    checks = {
        "initial_end_to_end_p95": {
            "actual": distributions["initial_end_to_end_seconds"]["p95"],
            "limit": thresholds["initial_end_to_end_p95_seconds_max"],
        },
        "urgent_replan_end_to_end_p95": {
            "actual": distributions["urgent_replan_end_to_end_seconds"]["p95"],
            "limit": thresholds["urgent_replan_end_to_end_p95_seconds_max"],
        },
        "non_solving_stages_p95": {
            "actual": non_solving,
            "limit": thresholds["non_solving_stages_p95_seconds_max"],
        },
        "presentation_api_p95": {
            "actual": distributions["presentation_api_max_seconds"]["p95"],
            "limit": thresholds["presentation_api_p95_seconds_max"],
        },
        "job_state_api_p95": {
            "actual": distributions["job_state_api_max_seconds"]["p95"],
            "limit": thresholds["job_state_api_p95_seconds_max"],
        },
        "backend_peak_rss_p95": {
            "actual": distributions["backend_peak_rss_bytes"]["p95"],
            "limit": thresholds["backend_peak_rss_p95_bytes_max"],
        },
    }
    for check in checks.values():
        check["status"] = (
            "PASS"
            if cast(float, check["actual"]) <= cast(float, check["limit"])
            else "FAIL"
        )
    hard_gate = cast(Mapping[str, object], summary["gates"])
    checks["validator_and_change_report_5_of_5"] = {
        "actual": 5
        if hard_gate["measured_initial_status_and_validator_5_of_5"]
        and hard_gate["measured_replan_status_validator_change_report_5_of_5"]
        else 0,
        "limit": thresholds["validator_and_change_report_required_passes"],
        "status": (
            "PASS"
            if hard_gate["measured_initial_status_and_validator_5_of_5"]
            and hard_gate["measured_replan_status_validator_change_report_5_of_5"]
            else "FAIL"
        ),
    }
    return {
        "status": (
            "PASS"
            if all(check["status"] == "PASS" for check in checks.values())
            else "FAIL"
        ),
        "checks": checks,
        "threshold_classification": "DEMO_RELEASE_TARGET_NOT_PRODUCTION_SLA",
    }


__all__ = [
    "FORMAL_PROTOCOL_VERSION",
    "FORMAL_SAMPLE_VERSION",
    "FORMAL_SUITE_VERSION",
    "FormalBenchmarkError",
    "FormalProtocol",
    "PROFILE_NAMES",
    "SAMPLE_ROLES",
    "attach_rss_measurement",
    "distribution",
    "fingerprint",
    "load_formal_protocol",
    "nearest_rank",
    "run_formal_sample",
    "showcase_thresholds",
    "summarize_profile",
]
