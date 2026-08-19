"""TEST-IMPORT-ADAPTER-001 staging replay integration for reference files."""

from __future__ import annotations

import csv
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

from alembic import command
from alembic.config import Config
from openpyxl import Workbook
import pytest
from sqlalchemy import Engine, create_engine, text

from app.importers import (
    ImportStagingError,
    REFERENCE_FILE_ADAPTER_ID,
    REFERENCE_FILE_ADAPTER_VERSION,
    REFERENCE_HEADERS,
    REFERENCE_SHEET_NAME,
    ReferenceFileAdapter,
    SourceFileManifest,
    StagingDataPlane,
    StagingErrorCode,
    SyntheticImportProvenance,
)
from app.infrastructure.import_staging_repository import (
    SqlAlchemyImportStagingRepository,
)

TEST_ID = "TEST-IMPORT-ADAPTER-001"
ROOT = Path(__file__).resolve().parents[3]
RECEIVED = datetime(2026, 8, 19, 5, 0, tzinfo=UTC)
ROWS = (
    ("factory", "FACTORY-001", '{"factory_code":"SYNTHETIC"}'),
    ("resource", "RESOURCE-001", '{"resource_code":"SYNTHETIC-R1"}'),
)


def _alembic_config(database_url: str) -> Config:
    configuration = Config(str(ROOT / "alembic.ini"))
    configuration.set_main_option(
        "script_location",
        str(ROOT / "backend" / "migrations"),
    )
    configuration.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return configuration


def _database(tmp_path: Path) -> Engine:
    database_url = f"sqlite:///{(tmp_path / 'reference-adapter.db').as_posix()}"
    command.upgrade(_alembic_config(database_url), "head")
    return create_engine(database_url)


def _provenance() -> SyntheticImportProvenance:
    return SyntheticImportProvenance(
        scenario_id="SIM-ADAPTER-001",
        scenario_version="1.0.0",
        seed=4104,
        factory_profile_id="PROFILE-ADAPTER-001",
        profile_version="1.0.0",
        generator_id="GENERATOR-ADAPTER-TEST",
        generator_version="1.0.0",
    )


def _source(
    relative_path: str,
    *,
    batch_id: str,
    idempotency_key: str,
    received_at: datetime = RECEIVED,
) -> SourceFileManifest:
    return SourceFileManifest(
        adapter_id=REFERENCE_FILE_ADAPTER_ID,
        adapter_version=REFERENCE_FILE_ADAPTER_VERSION,
        relative_path=relative_path,
        batch_id=batch_id,
        idempotency_key=idempotency_key,
        source_system="synthetic-reference-file",
        source_version="source.v1",
        received_at=received_at,
        data_plane=StagingDataPlane.SIMULATION,
        synthetic_provenance=_provenance(),
    )


def _write_csv(path: Path, rows: tuple[tuple[str, str, str], ...] = ROWS) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(REFERENCE_HEADERS)
        writer.writerows(rows)


def _write_xlsx(path: Path) -> None:
    workbook = Workbook()
    worksheet = workbook.active
    assert worksheet is not None
    worksheet.title = REFERENCE_SHEET_NAME
    worksheet.append(REFERENCE_HEADERS)
    for row in ROWS:
        worksheet.append(row)
    workbook.save(path)
    workbook.close()


def test_adapter_batches_persist_with_parity_exact_replay_and_conflict(
    tmp_path: Path,
) -> None:
    csv_path = tmp_path / "records.csv"
    xlsx_path = tmp_path / "records.xlsx"
    changed_path = tmp_path / "changed.csv"
    _write_csv(csv_path)
    _write_xlsx(xlsx_path)
    _write_csv(
        changed_path,
        rows=(("factory", "FACTORY-001", '{"factory_code":"CHANGED"}'),),
    )

    engine = _database(tmp_path)
    repository = SqlAlchemyImportStagingRepository(
        engine,
        data_plane=StagingDataPlane.SIMULATION,
    )
    adapter = ReferenceFileAdapter()
    csv_source = _source(
        csv_path.name,
        batch_id="BATCH-CSV-001",
        idempotency_key="IDEMPOTENCY-CSV-001",
    )
    try:
        csv_batch = adapter.prepare_batch(source_root=tmp_path, source=csv_source)
        created = repository.stage(csv_batch)
        assert created.replayed is False
        assert created.batch == csv_batch
        assert repository.get(csv_batch.batch_id) == csv_batch

        replay_source = replace(
            csv_source,
            batch_id="BATCH-CSV-RETRY",
            received_at=RECEIVED + timedelta(minutes=1),
        )
        replay_batch = adapter.prepare_batch(
            source_root=tmp_path,
            source=replay_source,
        )
        assert replay_batch.request_fingerprint == csv_batch.request_fingerprint
        replayed = repository.stage(replay_batch)
        assert replayed.replayed is True
        assert replayed.batch == csv_batch
        assert repository.get(replay_source.batch_id) is None

        changed_batch = adapter.prepare_batch(
            source_root=tmp_path,
            source=_source(
                changed_path.name,
                batch_id="BATCH-CSV-CHANGED",
                idempotency_key=csv_source.idempotency_key,
            ),
        )
        with pytest.raises(ImportStagingError) as captured:
            repository.stage(changed_batch)
        assert captured.value.code is StagingErrorCode.IDEMPOTENCY_CONFLICT

        xlsx_batch = adapter.prepare_batch(
            source_root=tmp_path,
            source=_source(
                xlsx_path.name,
                batch_id="BATCH-XLSX-001",
                idempotency_key="IDEMPOTENCY-XLSX-001",
            ),
        )
        xlsx_created = repository.stage(xlsx_batch)
        assert xlsx_created.replayed is False
        assert [row.row_identity for row in xlsx_batch.rows] == [
            row.row_identity for row in csv_batch.rows
        ]
        assert [row.raw_payload for row in xlsx_batch.rows] == [
            row.raw_payload for row in csv_batch.rows
        ]
        assert xlsx_batch.synthetic_provenance == csv_batch.synthetic_provenance
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT count(*) FROM raw_import_batches")) == 2
            assert connection.scalar(text("SELECT count(*) FROM raw_import_rows")) == 4
    finally:
        engine.dispose()
