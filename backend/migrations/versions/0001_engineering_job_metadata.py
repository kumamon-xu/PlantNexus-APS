"""Create business-neutral job reliability metadata tables.

Revision ID: 0001_engineering_job_metadata
Revises: None
Create Date: 2026-08-19
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_engineering_job_metadata"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_JOB_STATUSES = "'QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'STALLED'"


def upgrade() -> None:
    op.create_table(
        "engineering_job_records",
        sa.Column("job_id", sa.String(length=64), primary_key=True),
        sa.Column("job_kind", sa.String(length=80), nullable=False),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("worker_id", sa.String(length=160), nullable=True),
        sa.Column("failure_code", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            f"status IN ({_JOB_STATUSES})",
            name="ck_engineering_job_records_status",
        ),
        sa.CheckConstraint("attempt >= 0", name="ck_engineering_job_records_attempt"),
    )
    op.create_index(
        "ix_engineering_job_records_status_lease",
        "engineering_job_records",
        ["status", "lease_expires_at"],
        unique=False,
    )

    op.create_table(
        "engineering_idempotency_records",
        sa.Column("record_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("scope", sa.String(length=80), nullable=False),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("logical_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "scope",
            "idempotency_key",
            name="uq_engineering_idempotency_scope_key",
        ),
    )


def downgrade() -> None:
    op.drop_table("engineering_idempotency_records")
    op.drop_index(
        "ix_engineering_job_records_status_lease",
        table_name="engineering_job_records",
    )
    op.drop_table("engineering_job_records")
