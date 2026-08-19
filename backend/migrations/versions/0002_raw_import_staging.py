"""Create immutable Raw Staging batch and row tables.

Revision ID: 0002_raw_import_staging
Revises: 0001_engineering_job_metadata
Create Date: 2026-08-19
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_raw_import_staging"
down_revision: str | None = "0001_engineering_job_metadata"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "raw_import_batches",
        sa.Column("data_plane", sa.String(length=16), nullable=False),
        sa.Column("batch_id", sa.String(length=256), nullable=False),
        sa.Column("idempotency_key", sa.String(length=256), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("source_system", sa.String(length=256), nullable=False),
        sa.Column("source_version", sa.String(length=256), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("source_name", sa.String(length=256), nullable=False),
        sa.Column("media_type", sa.String(length=256), nullable=False),
        sa.Column("content_length_bytes", sa.BigInteger(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("synthetic_scenario_id", sa.String(length=256), nullable=True),
        sa.Column("synthetic_scenario_version", sa.String(length=256), nullable=True),
        sa.Column("synthetic_seed", sa.BigInteger(), nullable=True),
        sa.Column(
            "synthetic_factory_profile_id",
            sa.String(length=256),
            nullable=True,
        ),
        sa.Column("synthetic_profile_version", sa.String(length=256), nullable=True),
        sa.Column("synthetic_generator_id", sa.String(length=256), nullable=True),
        sa.Column("synthetic_generator_version", sa.String(length=256), nullable=True),
        sa.PrimaryKeyConstraint(
            "data_plane",
            "batch_id",
            name="pk_raw_import_batches",
        ),
        sa.UniqueConstraint(
            "data_plane",
            "source_system",
            "idempotency_key",
            name="uq_raw_import_batches_plane_source_idempotency",
        ),
        sa.CheckConstraint(
            "data_plane IN ('production', 'simulation')",
            name="ck_raw_import_batches_data_plane",
        ),
        sa.CheckConstraint(
            "content_length_bytes >= 0",
            name="ck_raw_import_batches_content_length",
        ),
        sa.CheckConstraint(
            "row_count >= 0",
            name="ck_raw_import_batches_row_count",
        ),
        sa.CheckConstraint(
            "synthetic_seed IS NULL OR synthetic_seed >= 0",
            name="ck_raw_import_batches_synthetic_seed",
        ),
        sa.CheckConstraint(
            "(data_plane = 'production' "
            "AND synthetic_scenario_id IS NULL "
            "AND synthetic_scenario_version IS NULL "
            "AND synthetic_seed IS NULL "
            "AND synthetic_factory_profile_id IS NULL "
            "AND synthetic_profile_version IS NULL "
            "AND synthetic_generator_id IS NULL "
            "AND synthetic_generator_version IS NULL) "
            "OR (data_plane = 'simulation' "
            "AND synthetic_scenario_id IS NOT NULL "
            "AND synthetic_scenario_version IS NOT NULL "
            "AND synthetic_seed IS NOT NULL "
            "AND synthetic_factory_profile_id IS NOT NULL "
            "AND synthetic_profile_version IS NOT NULL "
            "AND synthetic_generator_id IS NOT NULL "
            "AND synthetic_generator_version IS NOT NULL)",
            name="ck_raw_import_batches_synthetic_provenance",
        ),
    )
    op.create_index(
        "ix_raw_import_batches_source_received",
        "raw_import_batches",
        ["data_plane", "source_system", "received_at"],
        unique=False,
    )

    op.create_table(
        "raw_import_rows",
        sa.Column("data_plane", sa.String(length=16), nullable=False),
        sa.Column("batch_id", sa.String(length=256), nullable=False),
        sa.Column("row_identity", sa.String(length=256), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("source_location", sa.String(length=512), nullable=False),
        sa.Column("raw_payload", sa.LargeBinary(), nullable=False),
        sa.Column("payload_sha256", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint(
            "data_plane",
            "batch_id",
            "row_identity",
            name="pk_raw_import_rows",
        ),
        sa.ForeignKeyConstraint(
            ["data_plane", "batch_id"],
            ["raw_import_batches.data_plane", "raw_import_batches.batch_id"],
            name="fk_raw_import_rows_batch",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "data_plane",
            "batch_id",
            "position",
            name="uq_raw_import_rows_batch_position",
        ),
        sa.CheckConstraint(
            "position >= 0",
            name="ck_raw_import_rows_position",
        ),
    )


def downgrade() -> None:
    op.drop_table("raw_import_rows")
    op.drop_index(
        "ix_raw_import_batches_source_received",
        table_name="raw_import_batches",
    )
    op.drop_table("raw_import_batches")
