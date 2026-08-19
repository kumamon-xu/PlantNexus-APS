"""TEST-IMPORT-STAGING-001 durable replay, rollback, and isolation evidence."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import create_engine, func, select, text

from app.importers import (
    ImportStagingError,
    RawImportRow,
    StagedImportBatch,
    StagingDataPlane,
    StagingErrorCode,
    SyntheticImportProvenance,
)
from app.infrastructure.import_staging_repository import (
    SqlAlchemyImportStagingRepository,
)

ROOT = Path(__file__).resolve().parents[3]
RECEIVED = datetime(2026, 8, 19, 2, 0, tzinfo=UTC)


def _alembic_config(database_url: str) -> Config:
    configuration = Config(str(ROOT / "alembic.ini"))
    configuration.set_main_option(
        "script_location",
        str(ROOT / "backend" / "migrations"),
    )
    configuration.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return configuration


def _database(tmp_path: Path, name: str = "staging.db"):
    database_url = f"sqlite:///{(tmp_path / name).as_posix()}"
    command.upgrade(_alembic_config(database_url), "head")
    return create_engine(database_url)


def _provenance() -> SyntheticImportProvenance:
    return SyntheticImportProvenance(
        scenario_id="SIM-STAGING-001",
        scenario_version="1.0.0",
        seed=3103,
        factory_profile_id="PROFILE-STAGING-001",
        profile_version="1.0.0",
        generator_id="GENERATOR-STAGING",
        generator_version="1.0.0",
    )


def _batch(
    *,
    batch_id: str = "BATCH-001",
    idempotency_key: str = "IDEMPOTENCY-001",
    source_version: str = "source.v1",
    data_plane: StagingDataPlane = StagingDataPlane.SIMULATION,
    payloads: tuple[bytes, ...] = (b"row-one", b"\xff\x00row-two"),
) -> StagedImportBatch:
    file_content = b"\n".join(payloads)
    return StagedImportBatch(
        batch_id=batch_id,
        idempotency_key=idempotency_key,
        source_system="synthetic-inline",
        source_version=source_version,
        content_sha256=sha256(file_content).hexdigest(),
        source_name="inline-records.bin",
        media_type="application/octet-stream",
        content_length_bytes=len(file_content),
        received_at=RECEIVED,
        data_plane=data_plane,
        rows=tuple(
            RawImportRow(
                row_identity=f"ROW-{position:03d}",
                source_location=f"inline:{position}",
                raw_payload=payload,
            )
            for position, payload in enumerate(payloads, start=1)
        ),
        synthetic_provenance=(
            _provenance() if data_plane is StagingDataPlane.SIMULATION else None
        ),
    )


def test_atomic_stage_round_trip_exact_replay_and_conflict(tmp_path: Path) -> None:
    engine = _database(tmp_path)
    repository = SqlAlchemyImportStagingRepository(
        engine,
        data_plane=StagingDataPlane.SIMULATION,
    )
    batch = _batch()
    try:
        created = repository.stage(batch)
        assert created.replayed is False
        assert created.batch == batch
        loaded = repository.get(batch.batch_id)
        assert loaded == batch
        assert loaded is not None
        assert loaded.rows[1].raw_payload == b"\xff\x00row-two"

        replay_candidate = replace(
            batch,
            batch_id="BATCH-RETRY",
            received_at=RECEIVED + timedelta(minutes=1),
        )
        replayed = repository.stage(replay_candidate)
        assert replayed.replayed is True
        assert replayed.batch == batch
        assert repository.get("BATCH-RETRY") is None

        with pytest.raises(ImportStagingError) as captured:
            repository.stage(replace(batch, source_version="source.v2"))
        assert captured.value.code is StagingErrorCode.IDEMPOTENCY_CONFLICT
        with pytest.raises(ImportStagingError) as captured_content:
            repository.stage(_batch(batch_id="BATCH-CONTENT", payloads=(b"changed",)))
        assert captured_content.value.code is StagingErrorCode.IDEMPOTENCY_CONFLICT

        with engine.connect() as connection:
            assert connection.scalar(text("SELECT count(*) FROM raw_import_batches")) == 1
            assert connection.scalar(text("SELECT count(*) FROM raw_import_rows")) == 2
    finally:
        engine.dispose()


def test_transaction_failure_rolls_back_batch_and_rows_without_error_leak(
    tmp_path: Path,
) -> None:
    engine = _database(tmp_path, "rollback.db")
    repository = SqlAlchemyImportStagingRepository(
        engine,
        data_plane=StagingDataPlane.SIMULATION,
    )
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE TRIGGER reject_second_raw_row "
                    "BEFORE INSERT ON raw_import_rows "
                    "WHEN NEW.position = 1 "
                    "BEGIN SELECT RAISE(ABORT, 'password=do-not-leak'); END"
                )
            )
        with pytest.raises(ImportStagingError) as captured:
            repository.stage(_batch())
        assert captured.value.code is StagingErrorCode.STAGING_TRANSACTION_FAILED
        assert "do-not-leak" not in str(captured.value)
        assert "password" not in str(captured.value).lower()
        with engine.connect() as connection:
            batch_count = connection.scalar(
                select(func.count()).select_from(text("raw_import_batches"))
            )
            row_count = connection.scalar(
                select(func.count()).select_from(text("raw_import_rows"))
            )
        assert batch_count == 0
        assert row_count == 0
    finally:
        engine.dispose()


def test_repository_scope_prevents_cross_data_plane_access(tmp_path: Path) -> None:
    engine = _database(tmp_path, "isolation.db")
    production_repository = SqlAlchemyImportStagingRepository(
        engine,
        data_plane=StagingDataPlane.PRODUCTION,
    )
    simulation_repository = SqlAlchemyImportStagingRepository(
        engine,
        data_plane=StagingDataPlane.SIMULATION,
    )
    production_batch = _batch(data_plane=StagingDataPlane.PRODUCTION)
    simulation_batch = _batch(data_plane=StagingDataPlane.SIMULATION)
    try:
        production_repository.stage(production_batch)
        assert simulation_repository.get(production_batch.batch_id) is None
        simulation_repository.stage(simulation_batch)
        assert production_repository.get(production_batch.batch_id) == production_batch
        assert simulation_repository.get(simulation_batch.batch_id) == simulation_batch

        with pytest.raises(ImportStagingError) as captured:
            production_repository.stage(simulation_batch)
        assert captured.value.code is StagingErrorCode.DATA_PLANE_MISMATCH
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT count(*) FROM raw_import_batches")) == 2
    finally:
        engine.dispose()
