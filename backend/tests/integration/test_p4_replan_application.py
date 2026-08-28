"""TASK-P4-08 real migration/repository/application transaction tests."""

from __future__ import annotations

from collections.abc import Iterator
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
from threading import Barrier
from typing import Any, cast

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

from app.application.replan_application_check import (
    ReplanApplicationFixture,
    ReplanApplicationRuntime,
    build_replan_application_fixture,
    seed_replan_application_runtime,
)
from app.application.replan_application import ReplanApplicationService
from app.domain.execution_contracts import (
    canonical_contract_bytes,
    contract_fingerprint,
    solver_report_fingerprint,
)
from app.domain.replan_application import (
    ReplanApplicationError,
    ReplanApplicationFailure,
)
from app.infrastructure.replan_persistence import (
    ReplanAuditAction,
    ReplanAuditRecord,
)
from app.infrastructure.workspace_persistence import (
    DocumentWriteResult,
    PersistenceFailure,
    WorkspacePersistenceError,
)
from app.planning.strategies.lexicographic_replan import (
    LexicographicReplanResult,
)


ROOT = Path(__file__).resolve().parents[3]


class TerminalStrategy:
    def __init__(self, report: dict[str, object]) -> None:
        self._report = report

    def solve(
        self,
        _problem: Mapping[str, object],
        _policy: Mapping[str, object],
        _limits: object,
        *,
        base_schedule: Mapping[str, object],
        effective_locks: Mapping[str, object],
        replan_request: Mapping[str, object],
        planning_run_id: str,
        code_commit: str,
    ) -> LexicographicReplanResult:
        del (
            base_schedule,
            effective_locks,
            replan_request,
            planning_run_id,
            code_commit,
        )
        return LexicographicReplanResult(
            solver_report=deepcopy(self._report),
            round_reports=(),
            validation_reports=(),
        )


def _alembic_config(database_url: str) -> Config:
    configuration = Config(str(ROOT / "alembic.ini"))
    configuration.set_main_option(
        "script_location", str(ROOT / "backend" / "migrations")
    )
    configuration.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return configuration


@pytest.fixture
def engine(tmp_path: Path) -> Iterator[Engine]:
    database_url = f"sqlite:///{(tmp_path / 'p4-08.db').as_posix()}"
    configuration = _alembic_config(database_url)
    command.upgrade(configuration, "head")
    database = create_engine(database_url)
    try:
        yield database
    finally:
        database.dispose()
        command.downgrade(configuration, "base")


@pytest.fixture
def fixture() -> ReplanApplicationFixture:
    return build_replan_application_fixture(ROOT)


@pytest.fixture
def runtime(
    engine: Engine, fixture: ReplanApplicationFixture
) -> ReplanApplicationRuntime:
    return seed_replan_application_runtime(ROOT, engine, fixture)


def _count(engine: Engine, table: str) -> int:
    with engine.connect() as connection:
        return cast(
            int,
            connection.execute(text(f"SELECT count(*) FROM {table}")).scalar_one(),
        )


def test_result_application_commits_one_draft_and_exact_full_replay(
    engine: Engine,
    fixture: ReplanApplicationFixture,
    runtime: ReplanApplicationRuntime,
) -> None:
    base_before = canonical_contract_bytes(fixture.base_schedule)
    first = runtime.service.execute(fixture.input, fixture.context)
    replay = runtime.service.execute(fixture.input, fixture.context)

    assert first.exact_replay is False
    assert replay.exact_replay is True
    assert first.schedule_version is not None
    assert first.schedule_version["state"] == "DRAFT"
    assert first.schedule_version["source_kind"] == "DYNAMIC_REPLAN"
    assert first.schedule_version["parent_schedule_version"] == (
        fixture.request["base_schedule_version"]
    )
    assert first.schedule_version == replay.schedule_version
    assert first.solver_report == replay.solver_report
    assert first.validation_report == replay.validation_report
    assert first.kpi == replay.kpi
    assert first.change_report == replay.change_report
    assert first.change_report is not None
    assert first.change_report["operation_universe_count"] == 2
    assert first.change_report["new_schedule_version"] == {
        "schedule_version_version": "schedule-version.v2",
        "schedule_version_id": first.schedule_version["schedule_version_id"],
        "state": "DRAFT",
        "content_fingerprint": first.schedule_version["content_fingerprint"],
    }

    stored_base = runtime.schedule_repository.get(
        cast(str, fixture.base_schedule["schedule_version_id"])
    )
    assert stored_base is not None
    assert canonical_contract_bytes(stored_base) == base_before
    current = runtime.publication_repository.get_current()
    assert current is not None
    assert current.schedule_version_id == fixture.base_schedule["schedule_version_id"]
    assert _count(engine, "schedule_versions") == 2
    assert _count(engine, "replan_requests") == 1
    assert _count(engine, "replan_attempts") == 1
    assert _count(engine, "replan_results") == 1
    assert _count(engine, "replan_audit_records") == 3


def test_stale_current_publication_fails_before_solver_result_application(
    engine: Engine,
    fixture: ReplanApplicationFixture,
    runtime: ReplanApplicationRuntime,
) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE publication_current_references "
                "SET content_fingerprint = :fingerprint "
                "WHERE target = 'SIMULATION_INTERNAL'"
            ),
            {"fingerprint": "sha256:" + "f" * 64},
        )

    with pytest.raises(ReplanApplicationError) as captured:
        runtime.service.execute(fixture.input, fixture.context)
    assert captured.value.reason is ReplanApplicationFailure.STATE_CONFLICT
    assert captured.value.field == "current_publication"
    assert _count(engine, "schedule_versions") == 1
    assert _count(engine, "replan_results") == 0
    assert _count(engine, "replan_requests") == 1
    assert _count(engine, "replan_attempts") == 1


def test_result_audit_failure_rolls_back_draft_result_and_envelope(
    engine: Engine,
    fixture: ReplanApplicationFixture,
    runtime: ReplanApplicationRuntime,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = runtime.audit_repository.append_in_transaction

    def fail_result_audit(
        connection: Connection, record: ReplanAuditRecord
    ) -> DocumentWriteResult:
        if record.action is ReplanAuditAction.REPLAN_RESULT_APPENDED:
            raise WorkspacePersistenceError(
                PersistenceFailure.PERSISTENCE_FAILED,
                field="synthetic.result_audit",
                message="injected rollback proof",
            )
        return original(connection, record)

    monkeypatch.setattr(
        runtime.audit_repository,
        "append_in_transaction",
        fail_result_audit,
    )
    with pytest.raises(ReplanApplicationError) as captured:
        runtime.service.execute(fixture.input, fixture.context)
    assert captured.value.reason is ReplanApplicationFailure.PERSISTENCE_FAILED
    assert _count(engine, "schedule_versions") == 1
    assert _count(engine, "replan_results") == 0
    assert _count(engine, "replan_audit_records") == 2
    assert _count(engine, "replan_requests") == 1
    assert _count(engine, "replan_attempts") == 1


def test_same_request_with_different_idempotency_key_is_a_conflict(
    engine: Engine,
    fixture: ReplanApplicationFixture,
    runtime: ReplanApplicationRuntime,
) -> None:
    first = runtime.service.execute(fixture.input, fixture.context)
    changed_context = replace(
        fixture.context,
        idempotency_key_reference=contract_fingerprint(
            {"task": "TASK-P4-08", "command": "different-key"}
        ),
    )
    with pytest.raises(ReplanApplicationError) as captured:
        runtime.service.execute(fixture.input, changed_context)
    assert captured.value.reason in {
        ReplanApplicationFailure.IDEMPOTENCY_CONFLICT,
        ReplanApplicationFailure.LINEAGE_MISMATCH,
    }
    assert _count(engine, "schedule_versions") == 2
    assert _count(engine, "replan_attempts") == 1
    assert _count(engine, "replan_results") == 1
    assert runtime.schedule_repository.get(
        cast(str, first.schedule_version["schedule_version_id"])  # type: ignore[index]
    ) == first.schedule_version


def test_kpi_mismatch_leaves_only_retryable_intent(
    engine: Engine,
    fixture: ReplanApplicationFixture,
    runtime: ReplanApplicationRuntime,
) -> None:
    forged = deepcopy(fixture.after_kpi)
    cast(dict[str, object], forged["planning"])["makespan_seconds"] = 780
    forged.pop("kpi_id")
    forged["kpi_id"] = "kpi-" + sha256(
        canonical_contract_bytes(forged)
    ).hexdigest()
    changed_input = replace(fixture.input, after_kpi=forged)

    with pytest.raises(ReplanApplicationError) as captured:
        runtime.service.execute(changed_input, fixture.context)
    assert captured.value.reason is ReplanApplicationFailure.LINEAGE_MISMATCH
    assert captured.value.field == "after_kpi"
    assert _count(engine, "schedule_versions") == 1
    assert _count(engine, "replan_results") == 0
    assert _count(engine, "replan_audit_records") == 2


def test_concurrent_exact_command_has_one_commit_and_retryable_loser(
    engine: Engine,
    fixture: ReplanApplicationFixture,
    runtime: ReplanApplicationRuntime,
) -> None:
    barrier = Barrier(2)

    def invoke() -> object:
        barrier.wait()
        return runtime.service.execute(fixture.input, fixture.context)

    successes: list[object] = []
    failures: list[ReplanApplicationFailure] = []
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(invoke) for _ in range(2)]
        for future in futures:
            try:
                successes.append(future.result())
            except ReplanApplicationError as error:
                failures.append(error.reason)

    assert len(successes) >= 1
    assert len(successes) + len(failures) == 2
    assert set(failures) <= {
        ReplanApplicationFailure.PERSISTENCE_FAILED,
        ReplanApplicationFailure.LINEAGE_MISMATCH,
        ReplanApplicationFailure.IDEMPOTENCY_CONFLICT,
    }
    replay = runtime.service.execute(fixture.input, fixture.context)
    assert replay.exact_replay is True
    assert _count(engine, "schedule_versions") == 2
    assert _count(engine, "replan_requests") == 1
    assert _count(engine, "replan_attempts") == 1
    assert _count(engine, "replan_results") == 1
    assert _count(engine, "replan_audit_records") == 3


def test_no_candidate_terminal_report_is_durable_and_exactly_replayed(
    engine: Engine,
    fixture: ReplanApplicationFixture,
    runtime: ReplanApplicationRuntime,
) -> None:
    report = cast(
        dict[str, object],
        json.loads(
            (ROOT / "schemas/samples/solver-report.v2.synthetic.json").read_text(
                encoding="utf-8"
            )
        ),
    )
    report.update(
        {
            "replan_request": {
                "replan_request_version": "replan-request.v1",
                "request_id": fixture.request["request_id"],
                "request_fingerprint": fixture.request["request_fingerprint"],
            },
            "planning_run_id": fixture.context.planning_run_id,
            "base_problem": deepcopy(fixture.request["base_problem"]),
            "new_problem": deepcopy(fixture.request["new_problem"]),
            "policy": deepcopy(fixture.request["planning_policy"]),
            "limits": deepcopy(fixture.request["solve_limits"]),
        }
    )
    provenance = cast(dict[str, object], report["provenance"])
    provenance["code_commit"] = fixture.context.code_commit
    report["report_fingerprint"] = solver_report_fingerprint(report)
    report["report_id"] = "solver-report-" + cast(
        str, report["report_fingerprint"]
    ).removeprefix("sha256:")
    terminal_service = ReplanApplicationService(
        transaction_factory=engine.begin,
        schedule_repository=runtime.schedule_repository,
        publication_repository=runtime.publication_repository,
        snapshot_repository=runtime.snapshot_repository,
        request_repository=runtime.request_repository,
        lineage_repository=runtime.lineage_repository,
        audit_repository=runtime.audit_repository,
        strategy=cast(Any, TerminalStrategy(report)),
    )

    first = terminal_service.execute(fixture.input, fixture.context)
    replay = terminal_service.execute(fixture.input, fixture.context)
    assert first.result["planning_run_terminal_state"] == (
        "NO_SOLUTION_WITHIN_LIMIT"
    )
    assert first.schedule_version is None
    assert first.change_report is None
    assert first.solver_report == report
    assert replay.exact_replay is True
    assert replay.solver_report == report
    assert _count(engine, "schedule_versions") == 1
    assert _count(engine, "replan_results") == 1
    assert _count(engine, "replan_audit_records") == 3
