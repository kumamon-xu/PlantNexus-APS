"""TEST-P8-CANONICAL-INGRESS-001 durable transaction and migration evidence."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
from threading import Barrier
from typing import Any, Iterator, cast

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.exc import DBAPIError

from app.application.canonical_ingress import (
    CanonicalIngressApplicationService,
    CanonicalIngressPersistenceCode,
    CanonicalIngressPersistenceError,
)
from app.data_validation.canonical_ingress import (
    CanonicalIngressContract,
    canonical_json_bytes,
    idempotency_key_reference,
    request_fingerprint,
)
from app.infrastructure.canonical_ingress_repository import (
    SqlAlchemyCanonicalIngressRepository,
)
from app.infrastructure.workspace_persistence import WorkspaceDataPlane
from backend.tests.contract.p8_canonical_ingress_support import (
    ROOT,
    SCHEMA_DIRECTORY,
    request_document,
    trusted_context,
)


P8_TABLES = (
    "canonical_ingress_records",
    "planning_problems",
    "canonical_ingress_audit_records",
)
ARTIFACT_TABLES = (
    "canonical_ingress_records",
    "planning_snapshots",
    "planning_problems",
    "canonical_ingress_audit_records",
)


def _configuration(database_url: str) -> Config:
    configuration = Config(str(ROOT / "alembic.ini"))
    configuration.set_main_option(
        "script_location", str(ROOT / "backend" / "migrations")
    )
    configuration.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return configuration


@pytest.fixture
def migrated_engine(tmp_path: Path) -> Iterator[Engine]:
    database_url = f"sqlite:///{(tmp_path / 'p8-ingress.db').as_posix()}"
    configuration = _configuration(database_url)
    command.upgrade(configuration, "head")
    engine = create_engine(database_url)
    try:
        yield engine
    finally:
        engine.dispose()
        command.downgrade(configuration, "base")


def _service(
    engine: Engine, *, data_plane: WorkspaceDataPlane = WorkspaceDataPlane.SIMULATION
) -> CanonicalIngressApplicationService:
    return CanonicalIngressApplicationService(
        contract=CanonicalIngressContract.from_schema_directory(SCHEMA_DIRECTORY),
        repository=SqlAlchemyCanonicalIngressRepository(engine, data_plane=data_plane),
    )


def _counts(engine: Engine) -> dict[str, int]:
    with engine.connect() as connection:
        return {
            table: cast(int, connection.scalar(text(f"SELECT count(*) FROM {table}")))
            for table in ARTIFACT_TABLES
        }


def test_atomic_create_exact_replay_round_trip_and_append_only_guards(
    migrated_engine: Engine,
    record_testsuite_property: Any,
) -> None:
    for name, value in {
        "task_id": "TASK-P8-03",
        "test_id": "TEST-P8-CANONICAL-INGRESS-001",
        "diff_base": "c9efc2e8d35e29c139b9c819368047625f31724c",
        "validation_profile": "HIGH_RISK",
        "migration_head": "0006_canonical_ingress_application",
        "code_commit": os.environ.get("PLANTNEXUS_CODE_COMMIT", "WORKING_TREE"),
    }.items():
        record_testsuite_property(name, value)

    request = request_document()
    context = trusted_context(request)
    service = _service(migrated_engine)

    created = service.submit(canonical_json_bytes(request), context=context)
    replayed = _service(migrated_engine).submit(
        canonical_json_bytes(request), context=context
    )

    assert created.result["idempotency"]["outcome"] == "CREATED"
    assert replayed.result["idempotency"]["outcome"] == "REPLAYED"
    assert created.snapshot == replayed.snapshot
    assert created.problem == replayed.problem
    assert _counts(migrated_engine) == {table: 1 for table in ARTIFACT_TABLES}

    repository = SqlAlchemyCanonicalIngressRepository(
        migrated_engine, data_plane=WorkspaceDataPlane.SIMULATION
    )
    loaded = repository.get_by_idempotency(
        scope_fingerprint=context.idempotency_scope_fingerprint(),
        key_reference=idempotency_key_reference(request["idempotency_key"]),
    )
    assert loaded is not None
    assert b"p8-canonical-key-0001" not in loaded.canonical_bytes
    assert b'"idempotency_key"' not in loaded.canonical_bytes
    with pytest.raises(CanonicalIngressPersistenceError) as update_error:
        repository.update(loaded)
    assert update_error.value.code is CanonicalIngressPersistenceCode.APPEND_ONLY

    ingress_id = loaded.document["ingress_id"]
    with pytest.raises(DBAPIError):
        with migrated_engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE canonical_ingress_records "
                    "SET correlation_id='changed' WHERE ingress_id=:ingress_id"
                ),
                {"ingress_id": ingress_id},
            )
    with pytest.raises(DBAPIError):
        with migrated_engine.begin() as connection:
            connection.execute(
                text(
                    "DELETE FROM canonical_ingress_audit_records "
                    "WHERE ingress_id=:ingress_id"
                ),
                {"ingress_id": ingress_id},
            )
    assert _counts(migrated_engine) == {table: 1 for table in ARTIFACT_TABLES}


def test_idempotency_conflict_and_business_scope_isolation(
    migrated_engine: Engine,
) -> None:
    original = request_document()
    service = _service(migrated_engine)
    service.submit(canonical_json_bytes(original), context=trusted_context(original))

    conflicting = request_document(
        request_id="REQUEST-P8-CONFLICT",
        correlation_id="CORRELATION-P8-CONFLICT",
    )
    conflicting["planning_inputs"]["planning_policy"]["artifact_id"] = (
        "POLICY-P8-CONFLICT"
    )
    conflicting["request_fingerprint"] = request_fingerprint(conflicting)
    conflict = service.submit(
        canonical_json_bytes(conflicting), context=trusted_context(conflicting)
    )
    assert conflict.result["rejection"]["code"] == "IDEMPOTENCY_CONFLICT"

    isolated = request_document(
        request_id="REQUEST-P8-ISOLATED",
        correlation_id="CORRELATION-P8-ISOLATED",
    )
    isolated["requested_scope"]["tenant_id"] = "TENANT-P8-ISOLATED"
    isolated["request_fingerprint"] = request_fingerprint(isolated)
    isolated_result = service.submit(
        canonical_json_bytes(isolated), context=trusted_context(isolated)
    )
    assert isolated_result.result["idempotency"]["outcome"] == "CREATED"
    counts = _counts(migrated_engine)
    assert counts["canonical_ingress_records"] == 2
    assert counts["canonical_ingress_audit_records"] == 2
    assert counts["planning_snapshots"] == 1
    assert counts["planning_problems"] == 1

    production_repository = SqlAlchemyCanonicalIngressRepository(
        migrated_engine, data_plane=WorkspaceDataPlane.PRODUCTION
    )
    assert (
        production_repository.get_by_idempotency(
            scope_fingerprint=trusted_context(original).idempotency_scope_fingerprint(),
            key_reference=idempotency_key_reference(original["idempotency_key"]),
        )
        is None
    )


def test_failure_after_ingress_claim_rolls_back_every_artifact(
    migrated_engine: Engine,
) -> None:
    with migrated_engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TRIGGER trg_p8_injected_audit_failure "
                "BEFORE INSERT ON canonical_ingress_audit_records "
                "BEGIN SELECT RAISE(ABORT, 'injected audit failure'); END"
            )
        )
    request = request_document()

    outcome = _service(migrated_engine).submit(
        canonical_json_bytes(request), context=trusted_context(request)
    )

    assert outcome.result["rejection"]["code"] == "SYSTEM_ERROR"
    with migrated_engine.connect() as connection:
        assert (
            connection.scalar(text("SELECT count(*) FROM canonical_ingress_records"))
            == 0
        )
        assert connection.scalar(text("SELECT count(*) FROM planning_snapshots")) == 0
        assert connection.scalar(text("SELECT count(*) FROM planning_problems")) == 0
    with migrated_engine.begin() as connection:
        connection.execute(text("DROP TRIGGER trg_p8_injected_audit_failure"))


def test_concurrent_exact_requests_commit_one_resource_set(tmp_path: Path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'p8-concurrent.db').as_posix()}"
    configuration = _configuration(database_url)
    command.upgrade(configuration, "head")
    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    request = request_document()
    raw = canonical_json_bytes(request)
    context = trusted_context(request)
    barrier = Barrier(8)

    def submit() -> str:
        barrier.wait(timeout=10)
        outcome = _service(engine).submit(raw, context=context)
        assert outcome.result["disposition"] == "ACCEPTED"
        return cast(str, outcome.result["idempotency"]["outcome"])

    try:
        with ThreadPoolExecutor(max_workers=8) as executor:
            outcomes = list(executor.map(lambda _index: submit(), range(8)))
        assert outcomes.count("CREATED") == 1
        assert outcomes.count("REPLAYED") == 7
        assert _counts(engine) == {table: 1 for table in ARTIFACT_TABLES}
    finally:
        engine.dispose()
        command.downgrade(configuration, "base")


def test_populated_downgrade_is_declared_destructive_and_upgrade_replays(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{(tmp_path / 'p8-migration-replay.db').as_posix()}"
    configuration = _configuration(database_url)
    command.upgrade(configuration, "head")
    request = request_document()
    engine = create_engine(database_url)
    created = _service(engine).submit(
        canonical_json_bytes(request), context=trusted_context(request)
    )
    assert created.result["disposition"] == "ACCEPTED"
    engine.dispose()

    command.downgrade(configuration, "0005_replan_event_persistence")
    engine = create_engine(database_url)
    tables = set(inspect(engine).get_table_names())
    assert set(P8_TABLES).isdisjoint(tables)
    assert "planning_snapshots" in tables
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM planning_snapshots")) == 1
    engine.dispose()

    command.upgrade(configuration, "head")
    engine = create_engine(database_url)
    replay_after_upgrade = _service(engine).submit(
        canonical_json_bytes(request), context=trusted_context(request)
    )
    try:
        assert replay_after_upgrade.result["idempotency"]["outcome"] == "CREATED"
        assert _counts(engine) == {table: 1 for table in ARTIFACT_TABLES}
    finally:
        engine.dispose()
        command.downgrade(configuration, "base")
