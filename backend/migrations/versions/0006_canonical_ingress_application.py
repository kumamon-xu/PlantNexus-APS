"""Create P8 durable canonical-ingress, Problem and audit storage.

Revision ID: 0006_canonical_ingress_application
Revises: 0005_replan_event_persistence
Create Date: 2026-09-04

All three tables are append-only. Downgrade drops P8-03 records and therefore
has explicit data-loss semantics; operators must retain referenced immutable
evidence before executing it.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "0006_canonical_ingress_application"
down_revision: str | None = "0005_replan_event_persistence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_APPEND_ONLY_TABLES = (
    "canonical_ingress_records",
    "planning_problems",
    "canonical_ingress_audit_records",
)


def _stored_at() -> sa.Column[Any]:
    return sa.Column(
        "stored_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.current_timestamp(),
    )


def _fingerprint_check(column: str, name: str) -> sa.CheckConstraint:
    return sa.CheckConstraint(f"length({column}) = 71", name=name)


def _digest_check(column: str, name: str) -> sa.CheckConstraint:
    return sa.CheckConstraint(f"length({column}) = 64", name=name)


def _create_tables() -> None:
    op.create_table(
        "canonical_ingress_records",
        sa.Column("ingress_id", sa.String(length=256), nullable=False),
        sa.Column("data_plane", sa.String(length=16), nullable=False),
        sa.Column("environment", sa.String(length=32), nullable=False),
        sa.Column("tenant_id", sa.String(length=256), nullable=False),
        sa.Column("factory_id", sa.String(length=256), nullable=False),
        sa.Column("planning_scope_id", sa.String(length=256), nullable=False),
        sa.Column("request_id", sa.String(length=256), nullable=False),
        sa.Column("correlation_id", sa.String(length=256), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=71), nullable=False),
        sa.Column(
            "idempotency_scope_fingerprint", sa.String(length=71), nullable=False
        ),
        sa.Column("idempotency_key_reference", sa.String(length=71), nullable=False),
        sa.Column("payload_id", sa.String(length=256), nullable=False),
        sa.Column("payload_fingerprint", sa.String(length=71), nullable=False),
        sa.Column(
            "runtime_resolution_fingerprint", sa.String(length=71), nullable=False
        ),
        sa.Column("extension_set_fingerprint", sa.String(length=71), nullable=False),
        sa.Column("snapshot_id", sa.String(length=256), nullable=False),
        sa.Column("snapshot_hash", sa.String(length=71), nullable=False),
        sa.Column("problem_id", sa.String(length=256), nullable=False),
        sa.Column("problem_hash", sa.String(length=71), nullable=False),
        sa.Column("planning_run_id", sa.String(length=256), nullable=False),
        sa.Column("run_fingerprint", sa.String(length=71), nullable=False),
        sa.Column("result_id", sa.String(length=256), nullable=False),
        sa.Column("result_fingerprint", sa.String(length=71), nullable=False),
        sa.Column("audit_event_id", sa.String(length=256), nullable=False),
        sa.Column("audit_fingerprint", sa.String(length=71), nullable=False),
        sa.Column("occurred_at_utc", sa.String(length=32), nullable=False),
        sa.Column("record_json", sa.LargeBinary(), nullable=False),
        sa.Column("record_sha256", sa.String(length=64), nullable=False),
        _stored_at(),
        sa.PrimaryKeyConstraint("ingress_id", name="pk_canonical_ingress_records"),
        sa.UniqueConstraint(
            "idempotency_scope_fingerprint",
            "idempotency_key_reference",
            name="uq_canonical_ingress_idempotency",
        ),
        sa.UniqueConstraint(
            "data_plane",
            "tenant_id",
            "request_id",
            name="uq_canonical_ingress_scope_request",
        ),
        sa.UniqueConstraint(
            "planning_run_id", name="uq_canonical_ingress_planning_run"
        ),
        sa.UniqueConstraint("result_id", name="uq_canonical_ingress_result"),
        sa.CheckConstraint(
            "data_plane IN ('SIMULATION', 'PRODUCTION')",
            name="ck_canonical_ingress_plane",
        ),
        sa.CheckConstraint(
            "((data_plane = 'PRODUCTION' AND environment = 'PRODUCTION') OR "
            "(data_plane = 'SIMULATION' AND environment IN "
            "('DEVELOPMENT', 'TEST', 'BENCHMARK')))",
            name="ck_canonical_ingress_environment",
        ),
        _fingerprint_check(
            "request_fingerprint", "ck_canonical_ingress_request_fingerprint"
        ),
        _fingerprint_check(
            "idempotency_scope_fingerprint",
            "ck_canonical_ingress_idempotency_scope",
        ),
        _fingerprint_check(
            "idempotency_key_reference", "ck_canonical_ingress_idempotency_key"
        ),
        _fingerprint_check(
            "payload_fingerprint", "ck_canonical_ingress_payload_fingerprint"
        ),
        _fingerprint_check(
            "runtime_resolution_fingerprint",
            "ck_canonical_ingress_runtime_fingerprint",
        ),
        _fingerprint_check(
            "extension_set_fingerprint",
            "ck_canonical_ingress_extension_fingerprint",
        ),
        _fingerprint_check("snapshot_hash", "ck_canonical_ingress_snapshot_hash"),
        _fingerprint_check("problem_hash", "ck_canonical_ingress_problem_hash"),
        _fingerprint_check("run_fingerprint", "ck_canonical_ingress_run_fingerprint"),
        _fingerprint_check(
            "result_fingerprint", "ck_canonical_ingress_result_fingerprint"
        ),
        _fingerprint_check(
            "audit_fingerprint", "ck_canonical_ingress_audit_fingerprint"
        ),
        _digest_check("record_sha256", "ck_canonical_ingress_record_sha256"),
    )
    op.create_index(
        "ix_canonical_ingress_scope_time",
        "canonical_ingress_records",
        [
            "data_plane",
            "tenant_id",
            "factory_id",
            "planning_scope_id",
            "occurred_at_utc",
        ],
    )
    op.create_index(
        "ix_canonical_ingress_correlation",
        "canonical_ingress_records",
        ["data_plane", "correlation_id"],
    )

    op.create_table(
        "planning_problems",
        sa.Column("problem_hash", sa.String(length=71), nullable=False),
        sa.Column("problem_id", sa.String(length=256), nullable=False),
        sa.Column("data_plane", sa.String(length=16), nullable=False),
        sa.Column("snapshot_id", sa.String(length=256), nullable=False),
        sa.Column("snapshot_hash", sa.String(length=71), nullable=False),
        sa.Column("problem_version", sa.String(length=64), nullable=False),
        sa.Column("problem_builder_version", sa.String(length=64), nullable=False),
        sa.Column("canonicalization_version", sa.String(length=64), nullable=False),
        sa.Column("canonical_json", sa.LargeBinary(), nullable=False),
        sa.Column("canonical_sha256", sa.String(length=64), nullable=False),
        _stored_at(),
        sa.PrimaryKeyConstraint("problem_hash", name="pk_planning_problems"),
        sa.UniqueConstraint("problem_id", name="uq_planning_problems_id"),
        sa.CheckConstraint(
            "data_plane IN ('SIMULATION', 'PRODUCTION')",
            name="ck_planning_problems_plane",
        ),
        sa.CheckConstraint(
            "problem_version = 'planning-problem.v2'",
            name="ck_planning_problems_version",
        ),
        sa.CheckConstraint(
            "problem_builder_version = 'planning-problem-builder.v2'",
            name="ck_planning_problems_builder",
        ),
        sa.CheckConstraint(
            "canonicalization_version = 'canonical-json.v1'",
            name="ck_planning_problems_canonicalization",
        ),
        _fingerprint_check("problem_hash", "ck_planning_problems_hash"),
        _fingerprint_check("snapshot_hash", "ck_planning_problems_snapshot_hash"),
        _digest_check("canonical_sha256", "ck_planning_problems_sha256"),
    )
    op.create_index(
        "ix_planning_problems_plane_snapshot",
        "planning_problems",
        ["data_plane", "snapshot_id"],
    )

    op.create_table(
        "canonical_ingress_audit_records",
        sa.Column("audit_event_id", sa.String(length=256), nullable=False),
        sa.Column("audit_fingerprint", sa.String(length=71), nullable=False),
        sa.Column("data_plane", sa.String(length=16), nullable=False),
        sa.Column("ingress_id", sa.String(length=256), nullable=False),
        sa.Column("planning_run_id", sa.String(length=256), nullable=False),
        sa.Column("request_id", sa.String(length=256), nullable=False),
        sa.Column("correlation_id", sa.String(length=256), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=71), nullable=False),
        sa.Column(
            "idempotency_scope_fingerprint", sa.String(length=71), nullable=False
        ),
        sa.Column("idempotency_key_reference", sa.String(length=71), nullable=False),
        sa.Column("occurred_at_utc", sa.String(length=32), nullable=False),
        sa.Column("record_json", sa.LargeBinary(), nullable=False),
        sa.Column("record_sha256", sa.String(length=64), nullable=False),
        _stored_at(),
        sa.PrimaryKeyConstraint(
            "audit_event_id", name="pk_canonical_ingress_audit_records"
        ),
        sa.UniqueConstraint("ingress_id", name="uq_canonical_ingress_audit_ingress"),
        sa.CheckConstraint(
            "data_plane IN ('SIMULATION', 'PRODUCTION')",
            name="ck_canonical_ingress_audit_plane",
        ),
        _fingerprint_check(
            "audit_fingerprint", "ck_canonical_ingress_audit_fingerprint"
        ),
        _fingerprint_check(
            "request_fingerprint", "ck_canonical_ingress_audit_request_fingerprint"
        ),
        _fingerprint_check(
            "idempotency_scope_fingerprint",
            "ck_canonical_ingress_audit_idempotency_scope",
        ),
        _fingerprint_check(
            "idempotency_key_reference",
            "ck_canonical_ingress_audit_idempotency_key",
        ),
        _digest_check("record_sha256", "ck_canonical_ingress_audit_sha256"),
    )
    op.create_index(
        "ix_canonical_ingress_audit_run_time",
        "canonical_ingress_audit_records",
        ["data_plane", "planning_run_id", "occurred_at_utc"],
    )


def _create_sqlite_guards() -> None:
    for table in _APPEND_ONLY_TABLES:
        op.execute(
            f"CREATE TRIGGER trg_{table}_no_update BEFORE UPDATE ON {table} "
            f"BEGIN SELECT RAISE(ABORT, '{table} is append-only'); END"
        )
        op.execute(
            f"CREATE TRIGGER trg_{table}_no_delete BEFORE DELETE ON {table} "
            f"BEGIN SELECT RAISE(ABORT, '{table} is append-only'); END"
        )


def _create_postgresql_guards() -> None:
    op.execute(
        "CREATE FUNCTION reject_canonical_ingress_mutation() RETURNS trigger "
        "LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION '% is append-only', "
        "TG_TABLE_NAME; END; $$"
    )
    for table in _APPEND_ONLY_TABLES:
        op.execute(
            f"CREATE TRIGGER trg_{table}_no_update BEFORE UPDATE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION reject_canonical_ingress_mutation()"
        )
        op.execute(
            f"CREATE TRIGGER trg_{table}_no_delete BEFORE DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION reject_canonical_ingress_mutation()"
        )


def upgrade() -> None:
    _create_tables()
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        _create_sqlite_guards()
    elif dialect == "postgresql":
        _create_postgresql_guards()


def downgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        for table in _APPEND_ONLY_TABLES:
            op.execute(f"DROP TRIGGER trg_{table}_no_delete")
            op.execute(f"DROP TRIGGER trg_{table}_no_update")
    elif dialect == "postgresql":
        for table in _APPEND_ONLY_TABLES:
            op.execute(f"DROP TRIGGER trg_{table}_no_delete ON {table}")
            op.execute(f"DROP TRIGGER trg_{table}_no_update ON {table}")
        op.execute("DROP FUNCTION reject_canonical_ingress_mutation()")

    op.drop_index(
        "ix_canonical_ingress_audit_run_time",
        table_name="canonical_ingress_audit_records",
    )
    op.drop_table("canonical_ingress_audit_records")
    op.drop_index("ix_planning_problems_plane_snapshot", table_name="planning_problems")
    op.drop_table("planning_problems")
    op.drop_index(
        "ix_canonical_ingress_correlation", table_name="canonical_ingress_records"
    )
    op.drop_index(
        "ix_canonical_ingress_scope_time", table_name="canonical_ingress_records"
    )
    op.drop_table("canonical_ingress_records")
