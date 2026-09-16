"""Three application owners consume the same real SDK validation boundary."""

from collections.abc import Callable, Iterator
from pathlib import Path
from time import sleep
from typing import Any, cast

from alembic import command as alembic_command
import pytest
from sqlalchemy import Engine, text

from aps_extension_sdk import ValidationContext, ValidationOutput
from backend.tests.fixtures.p8_synthetic_extension import SyntheticValidationRule

from app.application.replan_application import ReplanApplicationService
from app.application.replan_application_check import (
    build_replan_application_fixture,
    seed_replan_application_runtime,
)
from app.application.schedule_commands import ScheduleCommandService
from app.application.schedule_version_lifecycle_check import (
    load_fixed_validated_output,
    lifecycle_context,
)
from app.application.schedule_versions import ValidatedSolutionToScheduleVersionService
from app.infrastructure import (
    SqlAlchemyAuditRepository,
    SqlAlchemyScheduleVersionRepository,
    WorkspaceDataPlane,
)
from app.planning.validation import ProblemScheduleValidator
from app.extensions.registry import LoadedRuntimeExtensionAdapter
from app.runtime_composition import compose_runtime, RuntimeProcess
from backend.tests.integration.test_schedule_command_transactions import (
    _move_command,
    _context,
    _submit_command,
)
from backend.tests.p8_runtime_extension_support import runtime_extension_fixture
from backend.tests.p8_solver_worker_support import (
    migrated_engine,
    materialize_worker_run,
    worker_for,
)
from backend.tests.security.test_p8_runtime_extension_security import (
    _RejectingValidationRule,
    VALIDATION_ID,
)

ROOT = Path(__file__).resolve().parents[3]


class CrashingValidationRule(SyntheticValidationRule):
    def validate(self, context: ValidationContext) -> ValidationOutput:
        raise RuntimeError("private-token")


class SlowValidationRule(SyntheticValidationRule):
    def validate(self, context: ValidationContext) -> ValidationOutput:
        sleep(0.1)
        return super().validate(context)


@pytest.fixture
def engine(tmp_path: Path) -> Iterator[Engine]:
    engine, configuration = migrated_engine(tmp_path / "p9.db")
    try:
        yield engine
    finally:
        engine.dispose()
        alembic_command.downgrade(configuration, "base")


def count(engine: Engine, table: str) -> int:
    with engine.connect() as connection:
        return cast(int, connection.scalar(text(f"SELECT count(*) FROM {table}")))


@pytest.mark.parametrize("source", ["first", "manual", "submit", "replan"])
@pytest.mark.parametrize("mode", ["pass", "reject", "crash", "timeout"])
def test_real_extension_validation_is_required_for_every_source(
    engine: Engine,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source: str,
    mode: str,
) -> None:
    extension = runtime_extension_fixture(
        tmp_path,
        database_url=str(engine.url),
        overrides={
            VALIDATION_ID: {
                "reject": _RejectingValidationRule,
                "crash": CrashingValidationRule,
                "timeout": SlowValidationRule,
            }[mode]
        }
        if mode != "pass"
        else None,
        invocation_timeout_ms=30 if mode == "timeout" else 100,
    )
    composition = compose_runtime(
        extension.settings,
        process=RuntimeProcess.WORKER,
        extension_artifacts=(extension.artifact,),
    )
    executor = composition.extension_product_executor
    scope = {
        "tenant_id": "TENANT-P8-APPLICATION",
        "factory_id": "FACTORY-001",
        "planning_scope_id": "PLANNING-P8-APPLICATION",
        "data_plane": "SIMULATION",
        "environment": "TEST",
    }
    admission = executor.candidate_admission(
        scope=scope,
        planning_run_id="p9-admission-test",
        runtime_identity=lambda: composition.descriptor.runtime_resolution,
    )
    execute: Callable[[], object]
    schedules: Any = None
    draft: Any = None
    try:
        if source == "first":
            created, orchestration, resolved = materialize_worker_run(engine)
            assert created.work_item is not None
            work = created.work_item.document
            worker = worker_for(engine, orchestration=orchestration, resolved=resolved)
            monkeypatch.setattr(worker, "_admission", admission)

            def execute_worker():
                return worker.execute(
                    planning_run_id=cast(str, work["planning_run_id"]),
                    work_item_id=cast(str, work["work_item_id"]),
                    worker_id="p9-worker",
                )

            execute = execute_worker
            initial = 0
        elif source == "replan":
            fixture = build_replan_application_fixture(ROOT)
            runtime = seed_replan_application_runtime(ROOT, engine, fixture)
            service = ReplanApplicationService(
                transaction_factory=engine.begin,
                schedule_repository=runtime.schedule_repository,
                publication_repository=runtime.publication_repository,
                snapshot_repository=runtime.snapshot_repository,
                request_repository=runtime.request_repository,
                lineage_repository=runtime.lineage_repository,
                audit_repository=runtime.audit_repository,
                admission=admission,
            )

            def execute_replan():
                return service.execute(fixture.input, fixture.context)

            execute = execute_replan

            initial = 1
        else:
            output, _ = load_fixed_validated_output(ROOT)
            schedules = SqlAlchemyScheduleVersionRepository(
                engine, data_plane=WorkspaceDataPlane.SIMULATION
            )
            audits = SqlAlchemyAuditRepository(
                engine, data_plane=WorkspaceDataPlane.SIMULATION
            )
            lifecycle = ValidatedSolutionToScheduleVersionService(
                data_plane="SIMULATION",
                transaction_factory=engine.begin,
                schedule_repository=schedules,
                audit_repository=audits,
            ).create_reviewable(output, lifecycle_context())
            service = ScheduleCommandService(
                data_plane="SIMULATION",
                transaction_factory=engine.begin,
                schedule_repository=cast(Any, schedules),
                audit_repository=cast(Any, audits),
                validator_factory=ProblemScheduleValidator,
                admission=admission,
            )
            move = _move_command(
                lifecycle.schedule_version, key="p9-admission-move-0001"
            )
            context = _context(lifecycle.audit_event_id, "edit")
            if source == "submit":
                core_service = ScheduleCommandService(
                    data_plane="SIMULATION",
                    transaction_factory=engine.begin,
                    schedule_repository=cast(Any, schedules),
                    audit_repository=cast(Any, audits),
                    validator_factory=ProblemScheduleValidator,
                )
                moved = core_service.execute(move, output.problem, context)
                draft = schedules.get(
                    cast(str, moved.new_version["schedule_version_id"])
                )
                assert draft is not None
                move = _submit_command(draft, key="p9-admission-submit-0001")

            def execute_command():
                return service.execute(move, output.problem, context)

            execute = execute_command

            initial = count(engine, "schedule_versions")
        if mode != "pass":
            with pytest.raises(Exception) as error:
                execute()
            assert "Extension" in str(error.value) or "validation" in str(error.value)
            assert "private-token" not in str(error.value)
            assert count(engine, "schedule_versions") == initial
            if source == "submit":
                assert (
                    schedules.get(cast(str, draft["schedule_version_id"]))["state"]
                    == "DRAFT"
                )
            if source == "replan":
                assert count(engine, "replan_results") == 0
        else:
            execute()
            assert count(engine, "schedule_versions") == initial + (
                0 if source == "submit" else 1
            )
        assert isinstance(composition.extension_adapter, LoadedRuntimeExtensionAdapter)
        metrics = composition.extension_adapter.safe_metrics()
        validation = next(
            row
            for row in metrics["contributions"]
            if row["contribution_id"] == VALIDATION_ID
        )
        if mode == "timeout":
            assert validation["timeout_count"] == 1
        elif mode == "crash":
            assert validation["failure_count"] == 1
        else:
            assert validation["success_count"] >= 1
    finally:
        composition.close()


@pytest.mark.parametrize("mutation", ["kit", "registry", "runtime", "scope"])
def test_runtime_admission_factory_rejects_mixed_authority(
    tmp_path: Path, mutation: str
):
    from copy import deepcopy
    from app.data_validation.canonical_ingress import runtime_resolution_fingerprint
    from app.extensions.contracts import RuntimeExtensionError

    extension = runtime_extension_fixture(
        tmp_path, database_url=f"sqlite:///{(tmp_path / 'identity.db').as_posix()}"
    )
    composition = compose_runtime(
        extension.settings,
        process=RuntimeProcess.WORKER,
        extension_artifacts=(extension.artifact,),
    )
    try:
        runtime = deepcopy(composition.descriptor.runtime_resolution)
        scope = {
            "tenant_id": "TENANT-P8-APPLICATION",
            "factory_id": "FACTORY-001",
            "planning_scope_id": "PLANNING-P8-APPLICATION",
        }
        if mutation == "kit":
            runtime["developer_kit_fingerprint"] = None
        elif mutation == "registry":
            runtime["extension_set"] = {}
        elif mutation == "scope":
            scope["tenant_id"] = "another-tenant"
        runtime["resolution_fingerprint"] = runtime_resolution_fingerprint(runtime)
        if mutation == "runtime":
            runtime["resolution_fingerprint"] = "sha256:" + "0" * 64
        with pytest.raises(RuntimeExtensionError):
            composition.extension_product_executor.candidate_admission(
                scope=scope,
                planning_run_id="p9-identity-test",
                runtime_identity=lambda: runtime,
            )
    finally:
        composition.close()
