"""TASK-P0-08 migration, lazy connectivity, Celery, and report evidence."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import cast

from alembic import command
from alembic.config import Config
from celery import Celery
from pydantic import SecretStr
from sqlalchemy import create_engine, inspect

from app.data_validation import validate_import_package
from app.domain.canonical_records import ImportPackageDocumentV2
from app.infrastructure.config import RuntimeEnvironment, Settings
from app.infrastructure.contract_check import main as engineering_check_main
from app.infrastructure.database import create_database_client
from app.infrastructure.import_staging_repository import (
    SqlAlchemyImportStagingRepository,
)
from app.infrastructure.snapshot_repository import SqlAlchemySnapshotRepository
from app.infrastructure.schedule_version_repository import (
    SqlAlchemyScheduleVersionRepository,
)
from app.infrastructure.workspace_persistence import WorkspaceDataPlane
from app.infrastructure.redis_client import create_redis_client
from app.importers import (
    RawImportRow,
    StagedImportBatch,
    StagingDataPlane,
    SyntheticImportProvenance,
)
from app.jobs.celery_app import create_celery_app
from app.normalization.order_expansion import expand_orders
from app.snapshots import (
    SnapshotDataPlane,
    build_planning_snapshot,
    import_package_id_for,
)

ROOT = Path(__file__).resolve().parents[3]


def _alembic_config(database_url: str) -> Config:
    configuration = Config(str(ROOT / "alembic.ini"))
    configuration.set_main_option(
        "script_location",
        str(ROOT / "backend" / "migrations"),
    )
    configuration.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return configuration


def test_empty_database_migration_upgrades_and_downgrades(tmp_path: Path) -> None:
    database_path = tmp_path / "engineering.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    configuration = _alembic_config(database_url)

    command.upgrade(configuration, "head")
    engine = create_engine(database_url)
    try:
        tables = set(inspect(engine).get_table_names())
        assert {
            "alembic_version",
            "engineering_idempotency_records",
            "engineering_job_records",
            "planning_snapshots",
            "raw_import_batches",
            "raw_import_rows",
            "schedule_versions",
            "audit_events",
            "publication_results",
            "publication_current_references",
            "export_jobs",
        } <= tables
        unique_constraints = inspect(engine).get_unique_constraints(
            "engineering_idempotency_records"
        )
        assert {constraint["name"] for constraint in unique_constraints} == {
            "uq_engineering_idempotency_scope_key"
        }
        raw_batch_unique_constraints = inspect(engine).get_unique_constraints(
            "raw_import_batches"
        )
        assert {constraint["name"] for constraint in raw_batch_unique_constraints} == {
            "uq_raw_import_batches_plane_source_idempotency"
        }
        raw_row_unique_constraints = inspect(engine).get_unique_constraints(
            "raw_import_rows"
        )
        assert {constraint["name"] for constraint in raw_row_unique_constraints} == {
            "uq_raw_import_rows_batch_position"
        }
        snapshot_unique_constraints = inspect(engine).get_unique_constraints(
            "planning_snapshots"
        )
        assert {constraint["name"] for constraint in snapshot_unique_constraints} == {
            "uq_planning_snapshots_snapshot_id"
        }
    finally:
        engine.dispose()

    command.downgrade(configuration, "base")
    engine = create_engine(database_url)
    try:
        tables_after = set(inspect(engine).get_table_names())
        assert "engineering_job_records" not in tables_after
        assert "engineering_idempotency_records" not in tables_after
        assert "raw_import_batches" not in tables_after
        assert "raw_import_rows" not in tables_after
        assert "planning_snapshots" not in tables_after
    finally:
        engine.dispose()


def test_populated_raw_staging_migration_downgrade_is_destructive_and_reversible(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "populated-staging.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    configuration = _alembic_config(database_url)
    command.upgrade(configuration, "0001_engineering_job_metadata")

    engine = create_engine(database_url)
    try:
        assert "raw_import_batches" not in set(inspect(engine).get_table_names())
    finally:
        engine.dispose()

    command.upgrade(configuration, "head")
    payload = b'{"opaque":"migration-sample"}'
    batch = StagedImportBatch(
        batch_id="MIGRATION-BATCH-001",
        idempotency_key="MIGRATION-IDEMPOTENCY-001",
        source_system="migration-synthetic",
        source_version="1.0.0",
        content_sha256=sha256(payload).hexdigest(),
        source_name="migration-sample.bin",
        media_type="application/octet-stream",
        content_length_bytes=len(payload),
        received_at=datetime(2026, 8, 19, tzinfo=UTC),
        data_plane=StagingDataPlane.SIMULATION,
        rows=(RawImportRow("ROW-001", "inline:1", payload),),
        synthetic_provenance=SyntheticImportProvenance(
            scenario_id="SIM-MIGRATION-001",
            scenario_version="1.0.0",
            seed=3103,
            factory_profile_id="PROFILE-MIGRATION-001",
            profile_version="1.0.0",
            generator_id="GENERATOR-MIGRATION",
            generator_version="1.0.0",
        ),
    )
    engine = create_engine(database_url)
    try:
        repository = SqlAlchemyImportStagingRepository(
            engine,
            data_plane=StagingDataPlane.SIMULATION,
        )
        assert repository.stage(batch).replayed is False
        assert repository.get(batch.batch_id) == batch
    finally:
        engine.dispose()

    command.downgrade(configuration, "0001_engineering_job_metadata")
    engine = create_engine(database_url)
    try:
        tables_after_downgrade = set(inspect(engine).get_table_names())
        assert "engineering_job_records" in tables_after_downgrade
        assert "engineering_idempotency_records" in tables_after_downgrade
        assert "raw_import_batches" not in tables_after_downgrade
        assert "raw_import_rows" not in tables_after_downgrade
    finally:
        engine.dispose()

    command.upgrade(configuration, "head")
    engine = create_engine(database_url)
    try:
        repository = SqlAlchemyImportStagingRepository(
            engine,
            data_plane=StagingDataPlane.SIMULATION,
        )
        assert repository.get(batch.batch_id) is None
    finally:
        engine.dispose()
    command.downgrade(configuration, "base")


def test_populated_snapshot_migration_downgrade_is_destructive_and_reversible(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "populated-snapshot.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    configuration = _alembic_config(database_url)
    command.upgrade(configuration, "0002_raw_import_staging")
    engine = create_engine(database_url)
    try:
        assert "planning_snapshots" not in set(inspect(engine).get_table_names())
    finally:
        engine.dispose()

    command.upgrade(configuration, "head")
    document = cast(
        dict[str, object],
        json.loads(
            (ROOT / "schemas/samples/import-package.v2.synthetic.json").read_text(
                encoding="utf-8"
            )
        ),
    )
    document["package_id"] = import_package_id_for(document)
    quality = validate_import_package(document).document
    expansion = expand_orders(cast(ImportPackageDocumentV2, document), quality)
    snapshot = build_planning_snapshot(
        document,
        quality,
        expansion,
        cutoff_at_utc="2026-08-20T00:00:00Z",
    )
    engine = create_engine(database_url)
    try:
        repository = SqlAlchemySnapshotRepository(
            engine,
            data_plane=SnapshotDataPlane.SIMULATION,
        )
        assert repository.put(snapshot).replayed is False
        assert repository.get_by_hash(snapshot.snapshot_hash) == snapshot
    finally:
        engine.dispose()

    command.downgrade(configuration, "0002_raw_import_staging")
    engine = create_engine(database_url)
    try:
        tables_after_downgrade = set(inspect(engine).get_table_names())
        assert "planning_snapshots" not in tables_after_downgrade
        assert "raw_import_batches" in tables_after_downgrade
        assert "raw_import_rows" in tables_after_downgrade
    finally:
        engine.dispose()

    command.upgrade(configuration, "head")
    engine = create_engine(database_url)
    try:
        repository = SqlAlchemySnapshotRepository(
            engine,
            data_plane=SnapshotDataPlane.SIMULATION,
        )
        assert repository.get_by_hash(snapshot.snapshot_hash) is None
    finally:
        engine.dispose()
    command.downgrade(configuration, "base")


def test_populated_p3_workspace_migration_downgrade_is_destructive_and_reversible(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "populated-p3-workspace.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    configuration = _alembic_config(database_url)
    command.upgrade(configuration, "0003_planning_snapshots")
    engine = create_engine(database_url)
    try:
        assert "schedule_versions" not in set(inspect(engine).get_table_names())
    finally:
        engine.dispose()

    command.upgrade(configuration, "head")
    schedule_document = cast(
        dict[str, object],
        json.loads(
            (ROOT / "schemas/samples/schedule-version.v1.synthetic.json").read_text(
                encoding="utf-8"
            )
        ),
    )
    engine = create_engine(database_url)
    try:
        repository = SqlAlchemyScheduleVersionRepository(
            engine,
            data_plane=WorkspaceDataPlane.SIMULATION,
        )
        assert repository.put(schedule_document).replayed is False
        assert repository.get("schedule-version-sim-001") == schedule_document
    finally:
        engine.dispose()

    command.downgrade(configuration, "0003_planning_snapshots")
    engine = create_engine(database_url)
    try:
        tables_after = set(inspect(engine).get_table_names())
        assert "planning_snapshots" in tables_after
        assert "schedule_versions" not in tables_after
        assert "audit_events" not in tables_after
        assert "publication_results" not in tables_after
        assert "publication_current_references" not in tables_after
        assert "export_jobs" not in tables_after
    finally:
        engine.dispose()

    command.upgrade(configuration, "head")
    engine = create_engine(database_url)
    try:
        repository = SqlAlchemyScheduleVersionRepository(
            engine,
            data_plane=WorkspaceDataPlane.SIMULATION,
        )
        assert repository.get("schedule-version-sim-001") is None
    finally:
        engine.dispose()
    command.downgrade(configuration, "base")


def test_database_engine_does_not_connect_until_probe(tmp_path: Path) -> None:
    database_path = tmp_path / "lazy.db"
    client = create_database_client(
        SecretStr(f"sqlite:///{database_path.as_posix()}"),
        timeout_seconds=1,
    )
    assert not database_path.exists()
    client.probe()
    assert database_path.exists()
    client.close()


def test_redis_client_does_not_connect_during_construction() -> None:
    client = create_redis_client(
        SecretStr("redis://127.0.0.1:1/0"),
        timeout_seconds=0.1,
    )
    client.close()


def test_celery_adapter_is_json_only_and_registers_no_business_tasks() -> None:
    application = create_celery_app(
        Settings(runtime_environment=RuntimeEnvironment.TEST)
    )
    assert isinstance(application, Celery)
    assert application.conf.accept_content == ["json"]
    assert application.conf.task_serializer == "json"
    assert application.conf.result_serializer == "json"
    assert application.conf.task_acks_late is True
    assert application.conf.task_reject_on_worker_lost is True
    assert application.conf.worker_prefetch_multiplier == 1
    custom_tasks = {
        task_name
        for task_name in application.tasks
        if not task_name.startswith("celery.")
    }
    assert custom_tasks == set()


def test_engineering_contract_check_writes_machine_report(tmp_path: Path) -> None:
    report_path = tmp_path / "engineering.json"
    exit_code = engineering_check_main(
        ["--root", str(ROOT), "--report", str(report_path)]
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert report["report_version"] == "engineering-skeleton-report.v1"
    assert report["status"] == "PASS"
    assert report["check_count"] == 6
    assert report["boundaries"]["solver"] == "NOT_INSTALLED"
