"""DEMO-PRESENT: strict unified views, lineage, filters, and read isolation."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import ValidationError

from app.infrastructure.schedule_version_repository import (
    SqlAlchemyScheduleVersionRepository,
)
from app.infrastructure.workspace_persistence import WorkspaceDataPlane

from plantnexus_demo.composition import DemoRuntime, create_demo_runtime
from plantnexus_demo.orchestration import DemoOperationError
from plantnexus_demo.persistence import RunDatabase, canonical_bytes, key_reference
from plantnexus_demo.presentation import (
    ComparisonPresentationQuery,
    DemoScheduleView,
    SchedulePresentationQuery,
    presentation_contract_schemas,
)
from plantnexus_demo.urgent import UrgentOrderCommand


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True, slots=True)
class _Scenario:
    runtime: DemoRuntime
    run_id: str
    base_version_id: str
    draft_version_id: str
    request_id: str


@pytest.fixture(scope="module")
def scenario(tmp_path_factory: pytest.TempPathFactory) -> Any:
    runtime = create_demo_runtime(
        repository_root=REPOSITORY_ROOT,
        runtime_root=tmp_path_factory.mktemp("presentation") / "runtime",
        auto_resume_queued=False,
    )
    reset = runtime.jobs.accept_reset(
        profile_name="smoke",
        idempotency_key="demo-presentation-reset-idempotency-0001",
        correlation_id="correlation-demo-presentation-reset",
    )
    reset_job = runtime.runner.wait(reset.job_id, timeout=30)
    assert reset_job.status == "SUCCEEDED" and reset_job.result is not None
    run_id = cast(str, reset_job.result["run_id"])
    plan = runtime.jobs.accept_initial_plan(
        expected_run_id=run_id,
        idempotency_key="demo-presentation-plan-idempotency-0001",
        correlation_id="correlation-demo-presentation-plan",
    )
    plan_job = runtime.runner.wait(plan.job_id, timeout=30)
    assert plan_job.status == "SUCCEEDED" and plan_job.result is not None
    base_version_id = cast(str, plan_job.result["schedule_version_id"])
    runtime.baseline.execute(
        expected_run_id=run_id,
        schedule_version_id=base_version_id,
        content_fingerprint=cast(str, plan_job.result["content_fingerprint"]),
        expected_state_revision=cast(int, plan_job.result["state_revision"]),
        confirmation="ACTIVATE_SIMULATION_BASELINE",
        idempotency_key_reference=key_reference(
            "demo-presentation-activate-idempotency-0001"
        ),
        correlation_id="correlation-demo-presentation-activate",
        occurred_at_utc="2026-09-02T10:02:00Z",
    )
    command = UrgentOrderCommand(
        command_version="cnc-demo-urgent-order-command.v1",
        expected_run_id=run_id,
        expected_base_version_id=base_version_id,
        route_template_id="CNC-ROUTE-4",
        quantity=4,
        due_at_local="2026-09-09T18:00:00",
        priority_class="URGENT",
        note="presentation contract fixture",
    )
    accepted = runtime.jobs.accept_urgent_order(
        command=command,
        idempotency_key="demo-presentation-urgent-idempotency-0001",
        correlation_id="correlation-demo-presentation-urgent",
    )
    urgent_job = runtime.runner.wait(accepted.job_id, timeout=45)
    assert urgent_job.status == "SUCCEEDED" and urgent_job.result is not None
    try:
        yield _Scenario(
            runtime=runtime,
            run_id=run_id,
            base_version_id=base_version_id,
            draft_version_id=cast(
                str, urgent_job.result["schedule_version_id"]
            ),
            request_id=cast(str, urgent_job.result["request_id"]),
        )
    finally:
        runtime.close()


def test_presentation_contracts_are_strict_and_queries_fail_closed() -> None:
    schemas = presentation_contract_schemas()
    assert set(schemas) == {
        "cnc-demo-factory-view.v1",
        "cnc-demo-schedule-view.v1",
        "cnc-demo-comparison-view.v1",
    }
    for schema in schemas.values():
        assert schema["additionalProperties"] is False
        for definition in schema.get("$defs", {}).values():
            if definition.get("type") == "object":
                assert definition["additionalProperties"] is False

    with pytest.raises(ValidationError):
        SchedulePresentationQuery.model_validate({"unknown": True})
    with pytest.raises(ValidationError):
        SchedulePresentationQuery(resource_ids=("b", "a"))
    with pytest.raises(ValidationError):
        SchedulePresentationQuery(
            start_at_utc="2026-09-10T00:00:00Z",
            end_at_utc="2026-09-09T00:00:00Z",
        )


def test_factory_and_v1_v2_schedule_views_share_time_semantics(
    scenario: _Scenario,
) -> None:
    service = scenario.runtime.presentation
    factory = service.factory()
    assert factory.run_id == scenario.run_id
    assert factory.factory.timezone == "Asia/Shanghai"
    assert factory.counts.workshops == 3
    assert factory.counts.production_lines == 3
    assert factory.counts.resource_groups == 7
    assert factory.counts.resources == 12
    assert factory.boundary.publishable is False
    assert all(
        interval.start.local.endswith("+08:00")
        for workshop in factory.factory.workshops
        for group in workshop.production_line.resource_groups
        for resource in group.resources
        for interval in resource.unavailable_intervals
    )

    base = service.schedule(
        scenario.base_version_id, SchedulePresentationQuery(limit=500)
    )
    draft = service.schedule(
        scenario.draft_version_id, SchedulePresentationQuery(limit=500)
    )
    assert base.version.contract_version == "schedule-version.v1"
    assert base.version.state == "PUBLISHED"
    assert draft.version.contract_version == "schedule-version.v2"
    assert draft.version.state == "DRAFT"
    assert len(base.orders) == 24
    assert len(draft.orders) == 25
    assert base.page.unfiltered_total == 102
    assert draft.page.unfiltered_total == 106
    assert len(base.resources) == len(draft.resources) == 12
    assert base.validation.status == draft.validation.status == "PASS"
    assert base.boundary.publishable is draft.boundary.publishable is False

    unchanged = service.comparison(
        scenario.request_id,
        ComparisonPresentationQuery(
            classifications=("UNCHANGED",), limit=500
        ),
    )
    assert unchanged.operations
    operation_id = unchanged.operations[0].operation_id
    base_assignment = {item.operation_id: item for item in base.assignments}[
        operation_id
    ]
    draft_assignment = {item.operation_id: item for item in draft.assignments}[
        operation_id
    ]
    assert base_assignment.start == draft_assignment.start
    assert base_assignment.end == draft_assignment.end
    assert base_assignment.resource_id == draft_assignment.resource_id

    detached = draft.model_dump(mode="python")
    detached["unexpected"] = True
    with pytest.raises(ValidationError):
        DemoScheduleView.model_validate(detached)


def test_filters_pages_change_authority_and_fingerprints_are_deterministic(
    scenario: _Scenario,
) -> None:
    service = scenario.runtime.presentation
    full = service.schedule(
        scenario.draft_version_id, SchedulePresentationQuery(limit=500)
    )
    first = full.assignments[0]
    query = SchedulePresentationQuery(
        resource_ids=(first.resource_id,),
        start_at_utc=first.start.utc,
        end_at_utc=first.end.utc,
        sort="RESOURCE_START_ASC",
        limit=5,
    )
    filtered = service.schedule(scenario.draft_version_id, query)
    replay = service.schedule(scenario.draft_version_id, query)
    assert filtered == replay
    assert filtered.view_fingerprint == replay.view_fingerprint
    assert filtered.page.returned <= 5
    assert filtered.page.filtered_total >= filtered.page.returned
    assert all(item.resource_id == first.resource_id for item in filtered.assignments)
    assert all(
        item.end.utc > first.start.utc and item.start.utc < first.end.utc
        for item in filtered.assignments
    )

    comparison = service.comparison(
        scenario.request_id,
        ComparisonPresentationQuery(
            classifications=(
                "ADDED",
                "CHANGED",
                "REMOVED_BY_FACT",
                "UNCHANGED",
            ),
            limit=500,
        ),
    )
    counts = comparison.change_counts
    assert comparison.operation_universe_count == sum(
        (
            counts.added,
            counts.changed,
            counts.removed_by_fact,
            counts.unchanged,
        )
    )
    assert comparison.page.returned == comparison.operation_universe_count
    assert comparison.provenance.validation_status == "PASS"
    assert all(
        item.classification
        in {"ADDED", "CHANGED", "REMOVED_BY_FACT", "UNCHANGED"}
        for item in comparison.operations
    )
    default = service.comparison(scenario.request_id)
    assert default.query.classifications == ("ADDED", "CHANGED")
    assert all(
        item.classification in {"ADDED", "CHANGED"}
        for item in default.operations
    )


def test_presentation_reads_do_not_mutate_formal_or_demo_state(
    scenario: _Scenario,
) -> None:
    runtime = scenario.runtime
    active = runtime.control.active_run()
    assert active is not None
    database = RunDatabase(
        repository_root=REPOSITORY_ROOT,
        database_path=runtime.paths.resolve_relative_database(
            active.database_relative_path
        ),
    )
    try:
        tables = (
            "schedule_versions",
            "publication_current_references",
            "replan_requests",
            "replan_attempts",
            "replan_results",
            "demo_artifacts",
            "demo_command_audit",
        )

        def counts() -> tuple[int, ...]:
            with database.engine.connect() as connection:
                return tuple(
                    cast(
                        int,
                        connection.exec_driver_sql(
                            f"SELECT COUNT(*) FROM {table}"  # noqa: S608
                        ).scalar_one(),
                    )
                    for table in tables
                )

        before_counts = counts()
        before_state = runtime.story_state()
        runtime.presentation.factory()
        runtime.presentation.schedule(scenario.base_version_id)
        runtime.presentation.schedule(scenario.draft_version_id)
        runtime.presentation.comparison(scenario.request_id)
        assert counts() == before_counts
        assert runtime.story_state() == before_state

        schedules = SqlAlchemyScheduleVersionRepository(
            database.engine, data_plane=WorkspaceDataPlane.SIMULATION
        )
        base = schedules.get(scenario.base_version_id)
        assert base is not None
        lineage = cast(dict[str, Any], base["lineage"])
        metadata = {
            (item["artifact_kind"], item["artifact_id"]): item
            for item in database.list_artifacts()
        }
        assert (
            "PLANNING_PROBLEM",
            lineage["problem"]["artifact_id"],
        ) in metadata
        assert metadata[
            ("PLANNING_PROBLEM", lineage["problem"]["artifact_id"])
        ]["document_version"] == "planning-problem.v2"
        assert metadata[("SNAPSHOT", lineage["snapshot"]["artifact_id"])][
            "document_version"
        ] == "planning-snapshot.v2"
        assert (
            "VALIDATION_REPORT",
            lineage["validation_report"]["artifact_id"],
        ) in metadata
    finally:
        database.close()


def test_artifact_mutation_fails_closed(tmp_path: Path) -> None:
    runtime = create_demo_runtime(
        repository_root=REPOSITORY_ROOT,
        runtime_root=tmp_path / "mutation-runtime",
        auto_resume_queued=False,
    )
    try:
        reset = runtime.jobs.accept_reset(
            profile_name="smoke",
            idempotency_key="demo-presentation-mutation-reset-0001",
            correlation_id="correlation-demo-presentation-mutation-reset",
        )
        reset_job = runtime.runner.wait(reset.job_id, timeout=30)
        assert reset_job.status == "SUCCEEDED" and reset_job.result is not None
        plan = runtime.jobs.accept_initial_plan(
            expected_run_id=cast(str, reset_job.result["run_id"]),
            idempotency_key="demo-presentation-mutation-plan-0001",
            correlation_id="correlation-demo-presentation-mutation-plan",
        )
        plan_job = runtime.runner.wait(plan.job_id, timeout=30)
        assert plan_job.status == "SUCCEEDED" and plan_job.result is not None
        version_id = cast(str, plan_job.result["schedule_version_id"])
        active = runtime.control.active_run()
        assert active is not None
        database = RunDatabase(
            repository_root=REPOSITORY_ROOT,
            database_path=runtime.paths.resolve_relative_database(
                active.database_relative_path
            ),
        )
        try:
            schedule = SqlAlchemyScheduleVersionRepository(
                database.engine, data_plane=WorkspaceDataPlane.SIMULATION
            ).get(version_id)
            assert schedule is not None
            kpi_reference = cast(dict[str, str], schedule["lineage"])["kpi"]
            kpi_id = cast(str, cast(dict[str, str], kpi_reference)["artifact_id"])
            kpi = database.get_artifact(artifact_kind="KPI", artifact_id=kpi_id)
            assert kpi is not None
            delivery = cast(dict[str, Any], kpi["delivery"])
            delivery["late_order_count"] = cast(
                int, delivery["late_order_count"]
            ) + 1
            payload = canonical_bytes(kpi)
            with database.engine.begin() as connection:
                connection.exec_driver_sql(
                    """
                    UPDATE demo_artifacts
                    SET canonical_json = ?, fingerprint = ?
                    WHERE artifact_kind = 'KPI' AND artifact_id = ?
                    """,
                    (payload, "sha256:" + sha256(payload).hexdigest(), kpi_id),
                )
        finally:
            database.close()
        with pytest.raises(DemoOperationError) as rejected:
            runtime.presentation.schedule(version_id)
        assert rejected.value.code == "PRESENTATION_LINEAGE_MISMATCH"
    finally:
        runtime.close()
