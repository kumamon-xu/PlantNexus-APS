"""Create durable PlanningRun orchestration, attempt, and work-item storage.

Revision ID: 0007_planning_run_orchestration
Revises: 0006_canonical_ingress_application
Create Date: 2026-09-05

Downgrade drops P8-04 run/attempt/work/transition/command/audit evidence and is
therefore destructive.  The P8-03 canonical ingress, Snapshot and Problem
tables remain intact so a stopped Runtime can rematerialize only after an
operator-approved rollback procedure.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op


revision: str = "0007_planning_run_orchestration"
down_revision: str | None = "0006_canonical_ingress_application"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_APPEND_ONLY_TABLES = (
    "planning_run_work_items",
    "planning_run_transitions",
    "planning_run_command_records",
    "planning_run_audit_records",
)


def _stored_at() -> sa.Column[Any]:
    return sa.Column(
        "stored_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.current_timestamp(),
    )


def _fingerprint(column: str, name: str) -> sa.CheckConstraint:
    return sa.CheckConstraint(f"length({column}) = 71", name=name)


def _digest(column: str, name: str) -> sa.CheckConstraint:
    return sa.CheckConstraint(f"length({column}) = 64", name=name)


def _plane(name: str, column: str = "data_plane") -> sa.CheckConstraint:
    return sa.CheckConstraint(f"{column} IN ('SIMULATION', 'PRODUCTION')", name=name)


def _create_tables() -> None:
    op.create_table(
        "planning_runs",
        sa.Column("planning_run_id", sa.String(length=256), nullable=False),
        sa.Column("ingress_id", sa.String(length=256), nullable=False),
        sa.Column("data_plane", sa.String(length=16), nullable=False),
        sa.Column("environment", sa.String(length=32), nullable=False),
        sa.Column("tenant_id", sa.String(length=256), nullable=False),
        sa.Column("factory_id", sa.String(length=256), nullable=False),
        sa.Column("planning_scope_id", sa.String(length=256), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("terminal", sa.Boolean(), nullable=False),
        sa.Column("run_fingerprint", sa.String(length=71), nullable=False),
        sa.Column("source_record_fingerprint", sa.String(length=71), nullable=False),
        sa.Column("initial_run_json", sa.LargeBinary(), nullable=False),
        sa.Column("initial_run_sha256", sa.String(length=64), nullable=False),
        sa.Column("prepared_artifacts_json", sa.LargeBinary(), nullable=False),
        sa.Column("prepared_artifacts_sha256", sa.String(length=64), nullable=False),
        sa.Column("current_run_json", sa.LargeBinary(), nullable=False),
        sa.Column("current_run_sha256", sa.String(length=64), nullable=False),
        sa.Column("updated_at_utc", sa.String(length=32), nullable=False),
        _stored_at(),
        sa.PrimaryKeyConstraint("planning_run_id", name="pk_planning_runs"),
        sa.UniqueConstraint("ingress_id", name="uq_planning_runs_ingress"),
        sa.ForeignKeyConstraint(
            ["ingress_id"],
            ["canonical_ingress_records.ingress_id"],
            name="fk_planning_runs_ingress",
        ),
        _plane("ck_planning_runs_plane"),
        sa.CheckConstraint("revision >= 1", name="ck_planning_runs_revision"),
        sa.CheckConstraint(
            "state IN ('CREATED','INGESTING','VALIDATING','SNAPSHOTTED',"
            "'BUILDING','SOLVING','SOLVED','VERIFYING','COMPLETED',"
            "'DATA_REJECTED','MODEL_INVALID','INFEASIBLE',"
            "'NO_SOLUTION_WITHIN_LIMIT','VALIDATION_FAILED','CANCELLED','FAILED')",
            name="ck_planning_runs_state",
        ),
        _fingerprint("run_fingerprint", "ck_planning_runs_run_fingerprint"),
        _fingerprint(
            "source_record_fingerprint", "ck_planning_runs_source_fingerprint"
        ),
        _digest("initial_run_sha256", "ck_planning_runs_initial_sha256"),
        _digest("prepared_artifacts_sha256", "ck_planning_runs_prepared_sha256"),
        _digest("current_run_sha256", "ck_planning_runs_current_sha256"),
    )
    op.create_index(
        "ix_planning_runs_scope_state",
        "planning_runs",
        ["data_plane", "tenant_id", "factory_id", "planning_scope_id", "state"],
    )

    op.create_table(
        "planning_run_attempts",
        sa.Column("attempt_id", sa.String(length=256), nullable=False),
        sa.Column("planning_run_id", sa.String(length=256), nullable=False),
        sa.Column("data_plane", sa.String(length=16), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("expected_run_revision", sa.Integer(), nullable=False),
        sa.Column("expected_run_state", sa.String(length=32), nullable=False),
        sa.Column("expected_run_fingerprint", sa.String(length=71), nullable=False),
        sa.Column(
            "runtime_resolution_fingerprint", sa.String(length=71), nullable=False
        ),
        sa.Column("extension_set_fingerprint", sa.String(length=71), nullable=False),
        sa.Column("available_at_utc", sa.String(length=32), nullable=False),
        sa.Column("timeout_at_utc", sa.String(length=32), nullable=False),
        sa.Column("attempt_json", sa.LargeBinary(), nullable=False),
        sa.Column("attempt_sha256", sa.String(length=64), nullable=False),
        sa.Column("updated_at_utc", sa.String(length=32), nullable=False),
        _stored_at(),
        sa.PrimaryKeyConstraint("attempt_id", name="pk_planning_run_attempts"),
        sa.UniqueConstraint(
            "planning_run_id",
            "attempt_number",
            name="uq_planning_run_attempt_number",
        ),
        sa.ForeignKeyConstraint(
            ["planning_run_id"],
            ["planning_runs.planning_run_id"],
            name="fk_planning_run_attempts_run",
        ),
        _plane("ck_planning_run_attempts_plane"),
        sa.CheckConstraint(
            "attempt_number >= 1 AND revision >= 1",
            name="ck_planning_run_attempts_revision",
        ),
        sa.CheckConstraint(
            "status IN ('QUEUED','ACTIVE','DISPATCH_FAILED','TIMED_OUT',"
            "'CANCEL_REQUESTED','CANCELLED','SUCCEEDED','FAILED')",
            name="ck_planning_run_attempts_status",
        ),
        _fingerprint(
            "expected_run_fingerprint", "ck_planning_run_attempts_expected_run"
        ),
        _fingerprint(
            "runtime_resolution_fingerprint",
            "ck_planning_run_attempts_runtime",
        ),
        _fingerprint("extension_set_fingerprint", "ck_planning_run_attempts_extension"),
        _digest("attempt_sha256", "ck_planning_run_attempts_sha256"),
    )
    op.create_index(
        "ix_planning_run_attempts_run_status",
        "planning_run_attempts",
        ["data_plane", "planning_run_id", "status", "attempt_number"],
    )

    op.create_table(
        "planning_run_work_items",
        sa.Column("work_item_id", sa.String(length=256), nullable=False),
        sa.Column("planning_run_id", sa.String(length=256), nullable=False),
        sa.Column("attempt_id", sa.String(length=256), nullable=False),
        sa.Column("data_plane", sa.String(length=16), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("expected_run_revision", sa.Integer(), nullable=False),
        sa.Column("expected_run_state", sa.String(length=32), nullable=False),
        sa.Column("expected_run_fingerprint", sa.String(length=71), nullable=False),
        sa.Column("work_item_fingerprint", sa.String(length=71), nullable=False),
        sa.Column("available_at_utc", sa.String(length=32), nullable=False),
        sa.Column("timeout_at_utc", sa.String(length=32), nullable=False),
        sa.Column("work_item_json", sa.LargeBinary(), nullable=False),
        sa.Column("work_item_sha256", sa.String(length=64), nullable=False),
        _stored_at(),
        sa.PrimaryKeyConstraint("work_item_id", name="pk_planning_run_work_items"),
        sa.UniqueConstraint("attempt_id", name="uq_planning_run_work_items_attempt"),
        sa.ForeignKeyConstraint(
            ["planning_run_id"],
            ["planning_runs.planning_run_id"],
            name="fk_planning_run_work_items_run",
        ),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["planning_run_attempts.attempt_id"],
            name="fk_planning_run_work_items_attempt",
        ),
        _plane("ck_planning_run_work_items_plane"),
        _fingerprint(
            "expected_run_fingerprint", "ck_planning_run_work_items_expected_run"
        ),
        _fingerprint("work_item_fingerprint", "ck_planning_run_work_items_fingerprint"),
        _digest("work_item_sha256", "ck_planning_run_work_items_sha256"),
    )
    op.create_index(
        "ix_planning_run_work_items_ready",
        "planning_run_work_items",
        ["data_plane", "available_at_utc", "timeout_at_utc", "attempt_number"],
    )

    op.create_table(
        "planning_run_audit_records",
        sa.Column("audit_event_id", sa.String(length=256), nullable=False),
        sa.Column("planning_run_id", sa.String(length=256), nullable=False),
        sa.Column("data_plane", sa.String(length=16), nullable=False),
        sa.Column("operation", sa.String(length=64), nullable=False),
        sa.Column("audit_fingerprint", sa.String(length=71), nullable=False),
        sa.Column("occurred_at_utc", sa.String(length=32), nullable=False),
        sa.Column("audit_json", sa.LargeBinary(), nullable=False),
        sa.Column("audit_sha256", sa.String(length=64), nullable=False),
        _stored_at(),
        sa.PrimaryKeyConstraint("audit_event_id", name="pk_planning_run_audit_records"),
        sa.ForeignKeyConstraint(
            ["planning_run_id"],
            ["planning_runs.planning_run_id"],
            name="fk_planning_run_audit_run",
        ),
        _plane("ck_planning_run_audit_plane"),
        _fingerprint("audit_fingerprint", "ck_planning_run_audit_fingerprint"),
        _digest("audit_sha256", "ck_planning_run_audit_sha256"),
    )
    op.create_index(
        "ix_planning_run_audit_run_time",
        "planning_run_audit_records",
        ["data_plane", "planning_run_id", "occurred_at_utc"],
    )

    op.create_table(
        "planning_run_transitions",
        sa.Column("planning_run_id", sa.String(length=256), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("data_plane", sa.String(length=16), nullable=False),
        sa.Column("from_state", sa.String(length=32), nullable=True),
        sa.Column("to_state", sa.String(length=32), nullable=False),
        sa.Column("before_run_fingerprint", sa.String(length=71), nullable=True),
        sa.Column("after_run_fingerprint", sa.String(length=71), nullable=False),
        sa.Column("audit_event_id", sa.String(length=256), nullable=False),
        sa.Column("audit_fingerprint", sa.String(length=71), nullable=False),
        sa.Column("occurred_at_utc", sa.String(length=32), nullable=False),
        sa.Column("transition_json", sa.LargeBinary(), nullable=False),
        sa.Column("transition_sha256", sa.String(length=64), nullable=False),
        _stored_at(),
        sa.PrimaryKeyConstraint(
            "planning_run_id", "sequence", name="pk_planning_run_transitions"
        ),
        sa.ForeignKeyConstraint(
            ["planning_run_id"],
            ["planning_runs.planning_run_id"],
            name="fk_planning_run_transitions_run",
        ),
        _plane("ck_planning_run_transitions_plane"),
        sa.CheckConstraint("sequence >= 0", name="ck_planning_run_transition_seq"),
        _fingerprint("after_run_fingerprint", "ck_planning_run_transition_after"),
        _fingerprint("audit_fingerprint", "ck_planning_run_transition_audit"),
        _digest("transition_sha256", "ck_planning_run_transition_sha256"),
    )

    op.create_table(
        "planning_run_command_records",
        sa.Column("command_id", sa.String(length=256), nullable=False),
        sa.Column("planning_run_id", sa.String(length=256), nullable=False),
        sa.Column("data_plane", sa.String(length=16), nullable=False),
        sa.Column("operation", sa.String(length=64), nullable=False),
        sa.Column("scope_fingerprint", sa.String(length=71), nullable=False),
        sa.Column("key_reference", sa.String(length=71), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=71), nullable=False),
        sa.Column("occurred_at_utc", sa.String(length=32), nullable=False),
        sa.Column("command_json", sa.LargeBinary(), nullable=False),
        sa.Column("command_sha256", sa.String(length=64), nullable=False),
        _stored_at(),
        sa.PrimaryKeyConstraint("command_id", name="pk_planning_run_commands"),
        sa.UniqueConstraint(
            "data_plane",
            "scope_fingerprint",
            "key_reference",
            name="uq_planning_run_command_idempotency",
        ),
        sa.ForeignKeyConstraint(
            ["planning_run_id"],
            ["planning_runs.planning_run_id"],
            name="fk_planning_run_commands_run",
        ),
        _plane("ck_planning_run_commands_plane"),
        _fingerprint("scope_fingerprint", "ck_planning_run_commands_scope"),
        _fingerprint("key_reference", "ck_planning_run_commands_key"),
        _fingerprint("request_fingerprint", "ck_planning_run_commands_request"),
        _digest("command_sha256", "ck_planning_run_commands_sha256"),
    )
    op.create_index(
        "ix_planning_run_commands_run_time",
        "planning_run_command_records",
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
    op.execute(
        "CREATE TRIGGER trg_planning_runs_no_delete BEFORE DELETE ON planning_runs "
        "BEGIN SELECT RAISE(ABORT, 'planning_runs cannot be deleted'); END"
    )
    op.execute(
        "CREATE TRIGGER trg_planning_runs_guard_update BEFORE UPDATE ON planning_runs "
        "WHEN NEW.planning_run_id != OLD.planning_run_id OR "
        "NEW.ingress_id != OLD.ingress_id OR NEW.data_plane != OLD.data_plane OR "
        "NEW.environment != OLD.environment OR NEW.tenant_id != OLD.tenant_id OR "
        "NEW.factory_id != OLD.factory_id OR "
        "NEW.planning_scope_id != OLD.planning_scope_id OR "
        "NEW.source_record_fingerprint != OLD.source_record_fingerprint OR "
        "NEW.initial_run_json != OLD.initial_run_json OR "
        "NEW.initial_run_sha256 != OLD.initial_run_sha256 OR "
        "NEW.prepared_artifacts_json != OLD.prepared_artifacts_json OR "
        "NEW.prepared_artifacts_sha256 != OLD.prepared_artifacts_sha256 OR "
        "NEW.revision != OLD.revision + 1 OR NOT ((OLD.state='CREATED' AND NEW.state IN "
        "('INGESTING','CANCELLED','FAILED')) OR (OLD.state='INGESTING' AND NEW.state IN "
        "('VALIDATING','DATA_REJECTED','CANCELLED','FAILED')) OR "
        "(OLD.state='VALIDATING' AND NEW.state IN "
        "('SNAPSHOTTED','DATA_REJECTED','CANCELLED','FAILED')) OR "
        "(OLD.state='SNAPSHOTTED' AND NEW.state IN ('BUILDING','CANCELLED','FAILED')) OR "
        "(OLD.state='BUILDING' AND NEW.state IN "
        "('SOLVING','MODEL_INVALID','CANCELLED','FAILED')) OR "
        "(OLD.state='SOLVING' AND NEW.state IN "
        "('SOLVED','MODEL_INVALID','INFEASIBLE','NO_SOLUTION_WITHIN_LIMIT','CANCELLED','FAILED')) OR "
        "(OLD.state='SOLVED' AND NEW.state IN ('VERIFYING','CANCELLED','FAILED')) OR "
        "(OLD.state='VERIFYING' AND NEW.state IN "
        "('COMPLETED','VALIDATION_FAILED','CANCELLED','FAILED'))) "
        "BEGIN SELECT RAISE(ABORT, 'invalid PlanningRun CAS transition'); END"
    )
    op.execute(
        "CREATE TRIGGER trg_planning_run_attempts_no_delete BEFORE DELETE ON "
        "planning_run_attempts BEGIN SELECT RAISE(ABORT, "
        "'planning_run_attempts cannot be deleted'); END"
    )
    op.execute(
        "CREATE TRIGGER trg_planning_run_attempts_guard_update BEFORE UPDATE ON "
        "planning_run_attempts WHEN NEW.attempt_id != OLD.attempt_id OR "
        "NEW.planning_run_id != OLD.planning_run_id OR "
        "NEW.data_plane != OLD.data_plane OR "
        "NEW.attempt_number != OLD.attempt_number OR "
        "NEW.expected_run_revision != OLD.expected_run_revision OR "
        "NEW.expected_run_state != OLD.expected_run_state OR "
        "NEW.expected_run_fingerprint != OLD.expected_run_fingerprint OR "
        "NEW.runtime_resolution_fingerprint != OLD.runtime_resolution_fingerprint OR "
        "NEW.extension_set_fingerprint != OLD.extension_set_fingerprint OR "
        "NEW.available_at_utc != OLD.available_at_utc OR "
        "NEW.timeout_at_utc != OLD.timeout_at_utc OR NEW.revision != OLD.revision + 1 OR "
        "NOT ((OLD.status='QUEUED' AND NEW.status IN "
        "('ACTIVE','DISPATCH_FAILED','TIMED_OUT','CANCELLED')) OR "
        "(OLD.status='ACTIVE' AND NEW.status IN "
        "('SUCCEEDED','FAILED','TIMED_OUT','CANCEL_REQUESTED','CANCELLED')) OR "
        "(OLD.status='CANCEL_REQUESTED' AND NEW.status IN "
        "('CANCELLED','FAILED','TIMED_OUT'))) "
        "BEGIN SELECT RAISE(ABORT, 'invalid PlanningRun attempt CAS transition'); END"
    )


def _create_postgresql_guards() -> None:
    op.execute(
        "CREATE FUNCTION reject_planning_run_append_mutation() RETURNS trigger "
        "LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION '% is append-only', "
        "TG_TABLE_NAME; END; $$"
    )
    for table in _APPEND_ONLY_TABLES:
        for action in ("update", "delete"):
            op.execute(
                f"CREATE TRIGGER trg_{table}_no_{action} BEFORE {action.upper()} ON {table} "
                "FOR EACH ROW EXECUTE FUNCTION reject_planning_run_append_mutation()"
            )
    op.execute(
        "CREATE FUNCTION guard_planning_run_delete() RETURNS trigger LANGUAGE plpgsql "
        "AS $$ BEGIN RAISE EXCEPTION 'PlanningRun records cannot be deleted'; END; $$"
    )
    op.execute(
        "CREATE TRIGGER trg_planning_runs_no_delete BEFORE DELETE ON planning_runs "
        "FOR EACH ROW EXECUTE FUNCTION guard_planning_run_delete()"
    )
    op.execute(
        "CREATE TRIGGER trg_planning_run_attempts_no_delete BEFORE DELETE ON "
        "planning_run_attempts FOR EACH ROW EXECUTE FUNCTION guard_planning_run_delete()"
    )
    op.execute(
        "CREATE FUNCTION guard_planning_run_update() RETURNS trigger LANGUAGE plpgsql "
        "AS $$ BEGIN IF ROW(NEW.planning_run_id, NEW.ingress_id, NEW.data_plane, "
        "NEW.environment, NEW.tenant_id, NEW.factory_id, NEW.planning_scope_id, "
        "NEW.source_record_fingerprint, NEW.initial_run_json, NEW.initial_run_sha256, "
        "NEW.prepared_artifacts_json, NEW.prepared_artifacts_sha256) IS DISTINCT FROM "
        "ROW(OLD.planning_run_id, OLD.ingress_id, OLD.data_plane, OLD.environment, "
        "OLD.tenant_id, OLD.factory_id, OLD.planning_scope_id, "
        "OLD.source_record_fingerprint, OLD.initial_run_json, OLD.initial_run_sha256, "
        "OLD.prepared_artifacts_json, OLD.prepared_artifacts_sha256) OR "
        "NEW.revision <> OLD.revision + 1 OR NOT ((OLD.state='CREATED' AND NEW.state IN "
        "('INGESTING','CANCELLED','FAILED')) OR (OLD.state='INGESTING' AND NEW.state IN "
        "('VALIDATING','DATA_REJECTED','CANCELLED','FAILED')) OR "
        "(OLD.state='VALIDATING' AND NEW.state IN "
        "('SNAPSHOTTED','DATA_REJECTED','CANCELLED','FAILED')) OR "
        "(OLD.state='SNAPSHOTTED' AND NEW.state IN ('BUILDING','CANCELLED','FAILED')) OR "
        "(OLD.state='BUILDING' AND NEW.state IN "
        "('SOLVING','MODEL_INVALID','CANCELLED','FAILED')) OR "
        "(OLD.state='SOLVING' AND NEW.state IN "
        "('SOLVED','MODEL_INVALID','INFEASIBLE','NO_SOLUTION_WITHIN_LIMIT',"
        "'CANCELLED','FAILED')) OR (OLD.state='SOLVED' AND NEW.state IN "
        "('VERIFYING','CANCELLED','FAILED')) OR (OLD.state='VERIFYING' AND NEW.state IN "
        "('COMPLETED','VALIDATION_FAILED','CANCELLED','FAILED'))) THEN RAISE EXCEPTION "
        "'invalid PlanningRun CAS transition'; END IF; RETURN NEW; END; $$"
    )
    op.execute(
        "CREATE TRIGGER trg_planning_runs_guard_update BEFORE UPDATE ON planning_runs "
        "FOR EACH ROW EXECUTE FUNCTION guard_planning_run_update()"
    )
    op.execute(
        "CREATE FUNCTION guard_planning_run_attempt_update() RETURNS trigger "
        "LANGUAGE plpgsql AS $$ BEGIN IF ROW(NEW.attempt_id, NEW.planning_run_id, "
        "NEW.data_plane, NEW.attempt_number, NEW.expected_run_revision, "
        "NEW.expected_run_state, NEW.expected_run_fingerprint, "
        "NEW.runtime_resolution_fingerprint, NEW.extension_set_fingerprint, "
        "NEW.available_at_utc, NEW.timeout_at_utc) IS DISTINCT FROM "
        "ROW(OLD.attempt_id, OLD.planning_run_id, OLD.data_plane, OLD.attempt_number, "
        "OLD.expected_run_revision, OLD.expected_run_state, "
        "OLD.expected_run_fingerprint, OLD.runtime_resolution_fingerprint, "
        "OLD.extension_set_fingerprint, OLD.available_at_utc, OLD.timeout_at_utc) OR "
        "NEW.revision <> OLD.revision + 1 OR NOT ((OLD.status='QUEUED' AND NEW.status IN "
        "('ACTIVE','DISPATCH_FAILED','TIMED_OUT','CANCELLED')) OR "
        "(OLD.status='ACTIVE' AND NEW.status IN "
        "('SUCCEEDED','FAILED','TIMED_OUT','CANCEL_REQUESTED','CANCELLED')) OR "
        "(OLD.status='CANCEL_REQUESTED' AND NEW.status IN "
        "('CANCELLED','FAILED','TIMED_OUT'))) THEN RAISE EXCEPTION "
        "'invalid PlanningRun attempt CAS transition'; END IF; RETURN NEW; END; $$"
    )
    op.execute(
        "CREATE TRIGGER trg_planning_run_attempts_guard_update BEFORE UPDATE ON "
        "planning_run_attempts FOR EACH ROW EXECUTE FUNCTION "
        "guard_planning_run_attempt_update()"
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
        op.execute("DROP TRIGGER trg_planning_run_attempts_guard_update")
        op.execute("DROP TRIGGER trg_planning_run_attempts_no_delete")
        op.execute("DROP TRIGGER trg_planning_runs_guard_update")
        op.execute("DROP TRIGGER trg_planning_runs_no_delete")
        for table in reversed(_APPEND_ONLY_TABLES):
            op.execute(f"DROP TRIGGER trg_{table}_no_delete")
            op.execute(f"DROP TRIGGER trg_{table}_no_update")
    elif dialect == "postgresql":
        op.execute(
            "DROP TRIGGER trg_planning_run_attempts_guard_update ON "
            "planning_run_attempts"
        )
        op.execute("DROP FUNCTION guard_planning_run_attempt_update()")
        op.execute("DROP TRIGGER trg_planning_runs_guard_update ON planning_runs")
        op.execute("DROP FUNCTION guard_planning_run_update()")
        op.execute(
            "DROP TRIGGER trg_planning_run_attempts_no_delete ON planning_run_attempts"
        )
        op.execute("DROP TRIGGER trg_planning_runs_no_delete ON planning_runs")
        op.execute("DROP FUNCTION guard_planning_run_delete()")
        for table in reversed(_APPEND_ONLY_TABLES):
            for action in ("delete", "update"):
                op.execute(f"DROP TRIGGER trg_{table}_no_{action} ON {table}")
        op.execute("DROP FUNCTION reject_planning_run_append_mutation()")

    op.drop_index(
        "ix_planning_run_commands_run_time",
        table_name="planning_run_command_records",
    )
    op.drop_table("planning_run_command_records")
    op.drop_table("planning_run_transitions")
    op.drop_index(
        "ix_planning_run_audit_run_time", table_name="planning_run_audit_records"
    )
    op.drop_table("planning_run_audit_records")
    op.drop_index(
        "ix_planning_run_work_items_ready", table_name="planning_run_work_items"
    )
    op.drop_table("planning_run_work_items")
    op.drop_index(
        "ix_planning_run_attempts_run_status", table_name="planning_run_attempts"
    )
    op.drop_table("planning_run_attempts")
    op.drop_index("ix_planning_runs_scope_state", table_name="planning_runs")
    op.drop_table("planning_runs")
