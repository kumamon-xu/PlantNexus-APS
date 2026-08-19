"""Create content-addressed, insert-only PlanningSnapshot storage.

Revision ID: 0003_planning_snapshots
Revises: 0002_raw_import_staging
Create Date: 2026-08-20
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_planning_snapshots"
down_revision: str | None = "0002_raw_import_staging"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "planning_snapshots",
        sa.Column("snapshot_hash", sa.String(length=71), nullable=False),
        sa.Column("snapshot_id", sa.String(length=256), nullable=False),
        sa.Column("data_plane", sa.String(length=16), nullable=False),
        sa.Column("snapshot_version", sa.String(length=64), nullable=False),
        sa.Column("canonicalization_version", sa.String(length=64), nullable=False),
        sa.Column("cutoff_at_utc", sa.String(length=32), nullable=False),
        sa.Column("canonical_sha256", sa.String(length=64), nullable=False),
        sa.Column("canonical_json", sa.LargeBinary(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.PrimaryKeyConstraint("snapshot_hash", name="pk_planning_snapshots"),
        sa.UniqueConstraint("snapshot_id", name="uq_planning_snapshots_snapshot_id"),
        sa.CheckConstraint(
            "data_plane IN ('production', 'simulation')",
            name="ck_planning_snapshots_data_plane",
        ),
        sa.CheckConstraint(
            "length(snapshot_hash) = 71",
            name="ck_planning_snapshots_hash_length",
        ),
        sa.CheckConstraint(
            "length(canonical_sha256) = 64",
            name="ck_planning_snapshots_canonical_sha_length",
        ),
        sa.CheckConstraint(
            "snapshot_version = 'planning-snapshot.v2'",
            name="ck_planning_snapshots_version",
        ),
        sa.CheckConstraint(
            "canonicalization_version = 'canonical-json.v1'",
            name="ck_planning_snapshots_canonicalization",
        ),
    )
    op.create_index(
        "ix_planning_snapshots_plane_cutoff",
        "planning_snapshots",
        ["data_plane", "cutoff_at_utc"],
        unique=False,
    )
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        op.execute(
            "CREATE TRIGGER trg_planning_snapshots_no_update "
            "BEFORE UPDATE ON planning_snapshots "
            "BEGIN SELECT RAISE(ABORT, 'planning_snapshots is insert-only'); END"
        )
        op.execute(
            "CREATE TRIGGER trg_planning_snapshots_no_delete "
            "BEFORE DELETE ON planning_snapshots "
            "BEGIN SELECT RAISE(ABORT, 'planning_snapshots is insert-only'); END"
        )
    elif dialect == "postgresql":
        op.execute(
            "CREATE FUNCTION reject_planning_snapshot_mutation() RETURNS trigger "
            "LANGUAGE plpgsql AS $$ BEGIN "
            "RAISE EXCEPTION 'planning_snapshots is insert-only'; END; $$"
        )
        op.execute(
            "CREATE TRIGGER trg_planning_snapshots_no_update "
            "BEFORE UPDATE ON planning_snapshots FOR EACH ROW "
            "EXECUTE FUNCTION reject_planning_snapshot_mutation()"
        )
        op.execute(
            "CREATE TRIGGER trg_planning_snapshots_no_delete "
            "BEFORE DELETE ON planning_snapshots FOR EACH ROW "
            "EXECUTE FUNCTION reject_planning_snapshot_mutation()"
        )


def downgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        op.execute("DROP TRIGGER trg_planning_snapshots_no_update")
        op.execute("DROP TRIGGER trg_planning_snapshots_no_delete")
    elif dialect == "postgresql":
        op.execute(
            "DROP TRIGGER trg_planning_snapshots_no_update ON planning_snapshots"
        )
        op.execute(
            "DROP TRIGGER trg_planning_snapshots_no_delete ON planning_snapshots"
        )
        op.execute("DROP FUNCTION reject_planning_snapshot_mutation()")
    op.drop_index(
        "ix_planning_snapshots_plane_cutoff",
        table_name="planning_snapshots",
    )
    op.drop_table("planning_snapshots")
