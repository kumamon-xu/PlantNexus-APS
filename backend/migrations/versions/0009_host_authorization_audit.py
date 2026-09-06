"""Create append-only Headless host authorization audit records.

Revision ID: 0009_host_authorization_audit
Revises: 0008_planning_run_solver_worker
Create Date: 2026-09-06

The table stores sanitized ALLOW/DENY decisions before Headless application
lookup.  It never stores bearer bytes or provider-specific claims.  Downgrade
deletes this P8-08 evidence and therefore requires an operator-approved export
under the future retention and backup policy.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0009_host_authorization_audit"
down_revision: str | None = "0008_planning_run_solver_worker"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "headless_authorization_audit_records"


def upgrade() -> None:
    op.create_table(
        _TABLE,
        sa.Column("audit_event_id", sa.String(length=64), nullable=False),
        sa.Column("data_plane", sa.String(length=16), nullable=False),
        sa.Column("environment", sa.String(length=32), nullable=False),
        sa.Column("operation_id", sa.String(length=64), nullable=False),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("reason", sa.String(length=64), nullable=False),
        sa.Column("actor_ref", sa.String(length=256), nullable=False),
        sa.Column("scope_fingerprint", sa.String(length=71), nullable=False),
        sa.Column("resource_reference", sa.String(length=71), nullable=True),
        sa.Column("correlation_id", sa.String(length=256), nullable=False),
        sa.Column("occurred_at_utc", sa.String(length=32), nullable=False),
        sa.Column("audit_fingerprint", sa.String(length=71), nullable=False),
        sa.Column("audit_json", sa.LargeBinary(), nullable=False),
        sa.Column("audit_sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "stored_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.PrimaryKeyConstraint(
            "audit_event_id", name="pk_headless_authorization_audit_records"
        ),
        sa.CheckConstraint(
            "data_plane IN ('SIMULATION','PRODUCTION')",
            name="ck_headless_authorization_audit_plane",
        ),
        sa.CheckConstraint(
            "outcome IN ('ALLOWED','DENIED')",
            name="ck_headless_authorization_audit_outcome",
        ),
        sa.CheckConstraint(
            "length(scope_fingerprint) = 71",
            name="ck_headless_authorization_audit_scope_fingerprint",
        ),
        sa.CheckConstraint(
            "resource_reference IS NULL OR length(resource_reference) = 71",
            name="ck_headless_authorization_audit_resource_reference",
        ),
        sa.CheckConstraint(
            "length(audit_fingerprint) = 71",
            name="ck_headless_authorization_audit_fingerprint",
        ),
        sa.CheckConstraint(
            "length(audit_sha256) = 64",
            name="ck_headless_authorization_audit_sha256",
        ),
    )
    op.create_index(
        "ix_headless_authorization_audit_scope_time",
        _TABLE,
        ["data_plane", "scope_fingerprint", "occurred_at_utc"],
    )
    op.create_index(
        "ix_headless_authorization_audit_correlation",
        _TABLE,
        ["data_plane", "correlation_id", "audit_event_id"],
    )

    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        op.execute(
            f"CREATE TRIGGER trg_{_TABLE}_no_update BEFORE UPDATE ON {_TABLE} "
            f"BEGIN SELECT RAISE(ABORT, '{_TABLE} is append-only'); END"
        )
        op.execute(
            f"CREATE TRIGGER trg_{_TABLE}_no_delete BEFORE DELETE ON {_TABLE} "
            f"BEGIN SELECT RAISE(ABORT, '{_TABLE} is append-only'); END"
        )
    elif dialect == "postgresql":
        op.execute(
            "CREATE FUNCTION reject_headless_authorization_audit_mutation() "
            "RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION "
            "'headless_authorization_audit_records is append-only'; END; $$"
        )
        for action in ("update", "delete"):
            op.execute(
                f"CREATE TRIGGER trg_{_TABLE}_no_{action} BEFORE {action.upper()} "
                f"ON {_TABLE} FOR EACH ROW EXECUTE FUNCTION "
                "reject_headless_authorization_audit_mutation()"
            )


def downgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        op.execute(f"DROP TRIGGER trg_{_TABLE}_no_delete")
        op.execute(f"DROP TRIGGER trg_{_TABLE}_no_update")
    elif dialect == "postgresql":
        op.execute(f"DROP TRIGGER trg_{_TABLE}_no_delete ON {_TABLE}")
        op.execute(f"DROP TRIGGER trg_{_TABLE}_no_update ON {_TABLE}")
        op.execute("DROP FUNCTION reject_headless_authorization_audit_mutation()")
    op.drop_index("ix_headless_authorization_audit_correlation", table_name=_TABLE)
    op.drop_index("ix_headless_authorization_audit_scope_time", table_name=_TABLE)
    op.drop_table(_TABLE)
