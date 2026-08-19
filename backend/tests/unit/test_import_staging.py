"""TEST-IMPORT-STAGING-001 pure Raw Staging contract evidence."""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, fields, replace
from datetime import UTC, datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from typing import cast

import pytest

from app.importers import (
    ImportStagingError,
    RawImportRow,
    StagedImportBatch,
    StagingDataPlane,
    StagingErrorCode,
    SyntheticImportProvenance,
    build_staged_import_batch,
)

ROOT = Path(__file__).resolve().parents[3]
RECEIVED = datetime(2026, 8, 19, 1, 2, 3, tzinfo=UTC)
RAW_PAYLOAD = b'{"opaque":"value"}'


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
    source_version: str = "source.v1",
    content: bytes = RAW_PAYLOAD,
    received_at: datetime = RECEIVED,
    data_plane: StagingDataPlane = StagingDataPlane.SIMULATION,
    rows: tuple[RawImportRow, ...] | None = None,
    synthetic_provenance: SyntheticImportProvenance | None = None,
) -> StagedImportBatch:
    if rows is None:
        rows = (
            RawImportRow(
                row_identity="ROW-001",
                source_location="inline:1",
                raw_payload=content,
            ),
        )
    if synthetic_provenance is None and data_plane is StagingDataPlane.SIMULATION:
        synthetic_provenance = _provenance()
    return StagedImportBatch(
        batch_id=batch_id,
        idempotency_key="IDEMPOTENCY-001",
        source_system="synthetic-inline",
        source_version=source_version,
        content_sha256=sha256(content).hexdigest(),
        source_name="inline-records.bin",
        media_type="application/octet-stream",
        content_length_bytes=len(content),
        received_at=received_at,
        data_plane=data_plane,
        rows=rows,
        synthetic_provenance=synthetic_provenance,
    )


def test_batch_rows_and_synthetic_provenance_are_immutable() -> None:
    batch = _batch()
    assert isinstance(batch.rows, tuple)
    assert batch.rows[0].raw_payload == RAW_PAYLOAD
    assert batch.rows[0].payload_sha256 == sha256(RAW_PAYLOAD).hexdigest()
    with pytest.raises(FrozenInstanceError):
        setattr(batch, "source_version", "changed")
    with pytest.raises(FrozenInstanceError):
        setattr(batch.rows[0], "source_location", "changed")
    assert batch.synthetic_provenance is not None
    with pytest.raises(FrozenInstanceError):
        setattr(batch.synthetic_provenance, "seed", 0)


def test_builder_freezes_an_iterable_without_parsing_raw_values() -> None:
    row = RawImportRow(
        row_identity="ROW-001",
        source_location="inline:1",
        raw_payload=b"\xff\x00not-json",
    )
    batch = build_staged_import_batch(
        batch_id="BATCH-001",
        idempotency_key="IDEMPOTENCY-001",
        source_system="synthetic-inline",
        source_version="source.v1",
        content_sha256=sha256(row.raw_payload).hexdigest(),
        source_name="inline-records.bin",
        media_type="application/octet-stream",
        content_length_bytes=len(row.raw_payload),
        received_at=RECEIVED,
        data_plane=StagingDataPlane.SIMULATION,
        rows=(item for item in [row]),
        synthetic_provenance=_provenance(),
    )
    assert batch.rows == (row,)
    assert batch.rows[0].raw_payload == b"\xff\x00not-json"


def test_replay_fingerprint_ignores_receipt_identity_but_covers_source_and_rows() -> None:
    batch = _batch()
    replay = replace(
        batch,
        batch_id="BATCH-RETRY",
        received_at=RECEIVED + timedelta(hours=1),
    )
    assert replay.request_fingerprint == batch.request_fingerprint
    assert replace(batch, source_version="source.v2").request_fingerprint != (
        batch.request_fingerprint
    )
    changed_row = RawImportRow(
        row_identity="ROW-001",
        source_location="inline:1",
        raw_payload=b"different bytes",
    )
    changed = replace(batch, rows=(changed_row,))
    assert changed.request_fingerprint != batch.request_fingerprint


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ({"source_version": ""}, StagingErrorCode.INVALID_STAGING_METADATA),
        ({"source_version": "   "}, StagingErrorCode.INVALID_STAGING_METADATA),
        ({"content_sha256": "not-a-digest"}, StagingErrorCode.INVALID_CONTENT_DIGEST),
        ({"source_name": "folder/source.csv"}, StagingErrorCode.INVALID_STAGING_METADATA),
        ({"content_length_bytes": -1}, StagingErrorCode.INVALID_STAGING_METADATA),
        (
            {"received_at": datetime(2026, 8, 19)},
            StagingErrorCode.INVALID_STAGING_METADATA,
        ),
        (
            {
                "received_at": datetime(
                    2026,
                    8,
                    19,
                    tzinfo=timezone(timedelta(hours=8)),
                )
            },
            StagingErrorCode.INVALID_STAGING_METADATA,
        ),
    ],
)
def test_invalid_metadata_has_stable_sanitized_errors(
    mutation: dict[str, object], expected_code: StagingErrorCode
) -> None:
    with pytest.raises(ImportStagingError) as captured:
        replace(_batch(), **mutation)
    assert captured.value.code is expected_code
    assert "folder/source.csv" not in str(captured.value)
    assert "not-a-digest" not in str(captured.value)


def test_duplicate_row_identity_is_rejected_before_persistence() -> None:
    duplicate_rows = (
        RawImportRow("ROW-001", "inline:1", b"first"),
        RawImportRow("ROW-001", "inline:2", b"second"),
    )
    with pytest.raises(ImportStagingError) as captured:
        _batch(rows=duplicate_rows)
    assert captured.value.code is StagingErrorCode.DUPLICATE_ROW_IDENTITY


def test_batch_rejects_non_row_values_with_a_stable_error() -> None:
    invalid_rows = cast(tuple[RawImportRow, ...], ("not-a-row",))
    with pytest.raises(ImportStagingError) as captured:
        replace(_batch(), rows=invalid_rows)
    assert captured.value.code is StagingErrorCode.INVALID_STAGING_METADATA


def test_production_and_simulation_provenance_are_mutually_exclusive() -> None:
    production = _batch(
        data_plane=StagingDataPlane.PRODUCTION,
        synthetic_provenance=None,
    )
    assert production.synthetic_provenance is None
    with pytest.raises(ImportStagingError) as captured_production:
        replace(production, synthetic_provenance=_provenance())
    assert captured_production.value.code is StagingErrorCode.DATA_PLANE_MISMATCH

    simulation = _batch()
    with pytest.raises(ImportStagingError) as captured_simulation:
        replace(simulation, synthetic_provenance=None)
    assert captured_simulation.value.code is StagingErrorCode.DATA_PLANE_MISMATCH

    with pytest.raises(ImportStagingError) as captured_unknown:
        replace(simulation, data_plane=cast(StagingDataPlane, "development"))
    assert captured_unknown.value.code is StagingErrorCode.INVALID_STAGING_METADATA


def test_raw_staging_contract_has_no_canonical_snapshot_or_solver_entrypoint() -> None:
    field_names = {field.name for field in fields(StagedImportBatch)}
    assert not field_names & {
        "canonical_records",
        "planning_snapshot",
        "planning_problem",
        "solver_input",
    }

    implementation_paths = [
        *sorted((ROOT / "backend" / "app" / "importers").glob("*.py")),
        ROOT / "backend" / "app" / "infrastructure" / "import_staging_repository.py",
    ]
    forbidden_roots = (
        "app.domain.canonical_records",
        "app.snapshots",
        "app.planning",
    )
    for path in implementation_paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imported_modules = {
            node.module or ""
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        }
        imported_modules.update(
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        )
        assert not any(
            module.startswith(forbidden_roots) for module in imported_modules
        ), path
