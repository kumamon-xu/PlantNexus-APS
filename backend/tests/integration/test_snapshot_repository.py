"""Integration evidence for content-addressed, isolated Snapshot persistence."""

from __future__ import annotations

from collections.abc import Iterator
from hashlib import sha256
import json
from pathlib import Path
from typing import cast

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import DBAPIError

from app.data_validation import validate_import_package
from app.domain.canonical_records import ImportPackageDocumentV2
from app.infrastructure.snapshot_repository import SqlAlchemySnapshotRepository
from app.normalization.order_expansion import expand_orders
from app.snapshots import (
    ImmutablePlanningSnapshot,
    SnapshotDataPlane,
    SnapshotError,
    SnapshotErrorCode,
    build_planning_snapshot,
    import_package_id_for,
)

ROOT = Path(__file__).resolve().parents[3]


def _alembic_config(database_url: str) -> Config:
    configuration = Config(str(ROOT / "alembic.ini"))
    configuration.set_main_option(
        "script_location", str(ROOT / "backend" / "migrations")
    )
    configuration.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return configuration


@pytest.fixture
def migrated_engine(tmp_path: Path) -> Iterator[Engine]:
    database_url = f"sqlite:///{(tmp_path / 'snapshots.db').as_posix()}"
    configuration = _alembic_config(database_url)
    command.upgrade(configuration, "head")
    engine = create_engine(database_url)
    try:
        yield engine
    finally:
        engine.dispose()
        command.downgrade(configuration, "base")


def _snapshot(*, synthetic: bool = True) -> ImmutablePlanningSnapshot:
    document = cast(
        dict[str, object],
        json.loads(
            (ROOT / "schemas/samples/import-package.v2.synthetic.json").read_text(
                encoding="utf-8"
            )
        ),
    )
    if not synthetic:
        document["synthetic"] = False
        document.pop("synthetic_provenance")
    document["package_id"] = import_package_id_for(document)
    quality = validate_import_package(document).document
    expansion = expand_orders(cast(ImportPackageDocumentV2, document), quality)
    return build_planning_snapshot(
        document,
        quality,
        expansion,
        cutoff_at_utc="2026-08-20T00:00:00Z",
    )


def test_insert_exact_replay_and_round_trip(migrated_engine: Engine) -> None:
    repository = SqlAlchemySnapshotRepository(
        migrated_engine, data_plane=SnapshotDataPlane.SIMULATION
    )
    snapshot = _snapshot()

    first = repository.put(snapshot)
    replay = repository.put(snapshot)

    assert first.replayed is False
    assert replay.replayed is True
    assert replay.snapshot == snapshot
    assert repository.get_by_id(snapshot.snapshot_id) == snapshot
    assert repository.get_by_hash(snapshot.snapshot_hash) == snapshot
    with migrated_engine.connect() as connection:
        row = connection.execute(
            text(
                "SELECT snapshot_id, snapshot_hash, data_plane, canonical_json, "
                "created_at FROM planning_snapshots"
            )
        ).one()
    assert row.snapshot_id == snapshot.snapshot_id
    assert row.snapshot_hash == snapshot.snapshot_hash
    assert row.data_plane == "simulation"
    assert bytes(row.canonical_json) == snapshot.canonical_bytes
    assert row.created_at is not None


def test_repository_and_database_reject_update_and_delete(
    migrated_engine: Engine,
) -> None:
    repository = SqlAlchemySnapshotRepository(
        migrated_engine, data_plane=SnapshotDataPlane.SIMULATION
    )
    snapshot = _snapshot()
    repository.put(snapshot)

    with pytest.raises(SnapshotError) as update_error:
        repository.update(snapshot)
    assert update_error.value.code is SnapshotErrorCode.IMMUTABLE_SNAPSHOT
    with pytest.raises(SnapshotError) as delete_error:
        repository.delete(snapshot.snapshot_id)
    assert delete_error.value.code is SnapshotErrorCode.IMMUTABLE_SNAPSHOT

    with pytest.raises(DBAPIError, match="insert-only"):
        with migrated_engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE planning_snapshots SET cutoff_at_utc = "
                    "'2099-01-01T00:00:00Z' WHERE snapshot_hash = :snapshot_hash"
                ),
                {"snapshot_hash": snapshot.snapshot_hash},
            )
    with pytest.raises(DBAPIError, match="insert-only"):
        with migrated_engine.begin() as connection:
            connection.execute(
                text("DELETE FROM planning_snapshots WHERE snapshot_hash = :snapshot_hash"),
                {"snapshot_hash": snapshot.snapshot_hash},
            )
    assert repository.get_by_hash(snapshot.snapshot_hash) == snapshot


def test_data_plane_guards_prevent_cross_plane_reads_and_writes(
    migrated_engine: Engine,
) -> None:
    simulation_repository = SqlAlchemySnapshotRepository(
        migrated_engine, data_plane=SnapshotDataPlane.SIMULATION
    )
    production_repository = SqlAlchemySnapshotRepository(
        migrated_engine, data_plane=SnapshotDataPlane.PRODUCTION
    )
    simulation = _snapshot()
    production = _snapshot(synthetic=False)

    simulation_repository.put(simulation)
    production_repository.put(production)
    assert production_repository.get_by_id(simulation.snapshot_id) is None
    assert simulation_repository.get_by_id(production.snapshot_id) is None

    with pytest.raises(SnapshotError) as wrong_write:
        production_repository.put(simulation)
    assert wrong_write.value.code is SnapshotErrorCode.DATA_PLANE_MISMATCH


def test_identity_bound_to_corrupt_content_is_an_explicit_conflict(
    migrated_engine: Engine,
) -> None:
    repository = SqlAlchemySnapshotRepository(
        migrated_engine, data_plane=SnapshotDataPlane.SIMULATION
    )
    snapshot = _snapshot()
    corrupt = b"{}"
    with migrated_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO planning_snapshots "
                "(snapshot_hash, snapshot_id, data_plane, snapshot_version, "
                "canonicalization_version, cutoff_at_utc, canonical_sha256, "
                "canonical_json) VALUES (:snapshot_hash, :snapshot_id, "
                "'simulation', 'planning-snapshot.v2', 'canonical-json.v1', "
                ":cutoff, :canonical_sha256, :canonical_json)"
            ),
            {
                "snapshot_hash": snapshot.snapshot_hash,
                "snapshot_id": snapshot.snapshot_id,
                "cutoff": "2026-08-20T00:00:00Z",
                "canonical_sha256": sha256(corrupt).hexdigest(),
                "canonical_json": corrupt,
            },
        )

    with pytest.raises(SnapshotError) as conflict:
        repository.put(snapshot)
    assert conflict.value.code is SnapshotErrorCode.CONTENT_CONFLICT


def test_invalid_query_identity_is_rejected_without_driver_detail(
    migrated_engine: Engine,
) -> None:
    repository = SqlAlchemySnapshotRepository(
        migrated_engine, data_plane=SnapshotDataPlane.SIMULATION
    )
    with pytest.raises(SnapshotError) as invalid_hash:
        repository.get_by_hash("not-a-hash")
    assert invalid_hash.value.code is SnapshotErrorCode.INVALID_SNAPSHOT_INPUT
    assert "sqlite" not in str(invalid_hash.value).lower()
