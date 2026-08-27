"""Create bounded P4 execution-event and replan persistence primitives.

Revision ID: 0005_replan_event_persistence
Revises: 0004_schedule_versions_audit_export_jobs
Create Date: 2026-08-27

The tables are Simulation-only storage primitives.  They do not project
execution facts, run a solver, create a ScheduleVersion, or authorize any
Production or external side effect.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_replan_event_persistence"
down_revision: str | None = "0004_schedule_versions_audit_export_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_APPEND_ONLY_TABLES = (
    "execution_event_ledger",
    "replan_requests",
    "replan_request_events",
    "replan_attempts",
    "replan_results",
    "replan_audit_records",
)


def _stored_at() -> sa.Column[object]:
    return sa.Column(
        "stored_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.current_timestamp(),
    )


def _simulation_check(name: str) -> sa.CheckConstraint:
    return sa.CheckConstraint("data_plane = 'SIMULATION'", name=name)


def _create_tables() -> None:
    op.create_table(
        "execution_event_ledger",
        sa.Column("data_plane", sa.String(length=16), nullable=False),
        sa.Column("event_id", sa.String(length=256), nullable=False),
        sa.Column("event_fingerprint", sa.String(length=71), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("environment", sa.String(length=32), nullable=False),
        sa.Column("factory_id", sa.String(length=256), nullable=False),
        sa.Column("planning_scope_id", sa.String(length=256), nullable=False),
        sa.Column("authority_id", sa.String(length=256), nullable=False),
        sa.Column("authority_scope", sa.String(length=768), nullable=False),
        sa.Column("stream_id", sa.String(length=256), nullable=False),
        sa.Column("stream_version", sa.String(length=64), nullable=False),
        sa.Column("source_position", sa.Integer(), nullable=False),
        sa.Column("occurred_at_utc", sa.String(length=32), nullable=False),
        sa.Column("received_at_utc", sa.String(length=32), nullable=False),
        sa.Column("correlation_id", sa.String(length=256), nullable=False),
        sa.Column("document_json", sa.LargeBinary(), nullable=False),
        sa.Column("document_sha256", sa.String(length=64), nullable=False),
        _stored_at(),
        sa.PrimaryKeyConstraint(
            "data_plane", "event_id", name="pk_execution_event_ledger"
        ),
        sa.UniqueConstraint(
            "data_plane",
            "authority_id",
            "stream_id",
            "stream_version",
            "source_position",
            name="uq_execution_event_ledger_stream_position",
        ),
        _simulation_check("ck_execution_event_ledger_plane"),
        sa.CheckConstraint(
            "source_position >= 1", name="ck_execution_event_ledger_position"
        ),
        sa.CheckConstraint(
            "length(event_fingerprint) = 71",
            name="ck_execution_event_ledger_fingerprint",
        ),
        sa.CheckConstraint(
            "length(document_sha256) = 64",
            name="ck_execution_event_ledger_document_sha256",
        ),
    )
    op.create_index(
        "ix_execution_event_ledger_scope_position",
        "execution_event_ledger",
        [
            "data_plane",
            "factory_id",
            "planning_scope_id",
            "authority_id",
            "stream_id",
            "stream_version",
            "source_position",
        ],
    )
    op.create_index(
        "ix_execution_event_ledger_correlation",
        "execution_event_ledger",
        ["data_plane", "correlation_id"],
    )

    op.create_table(
        "replan_projection_checkpoints",
        sa.Column("data_plane", sa.String(length=16), nullable=False),
        sa.Column("factory_id", sa.String(length=256), nullable=False),
        sa.Column("planning_scope_id", sa.String(length=256), nullable=False),
        sa.Column("authority_id", sa.String(length=256), nullable=False),
        sa.Column("stream_id", sa.String(length=256), nullable=False),
        sa.Column("stream_version", sa.String(length=64), nullable=False),
        sa.Column("last_applied_position", sa.Integer(), nullable=False),
        sa.Column("prefix_fingerprint", sa.String(length=71), nullable=False),
        sa.Column("fact_checkpoint_version", sa.String(length=128), nullable=False),
        sa.Column("fact_checkpoint_id", sa.String(length=256), nullable=False),
        sa.Column("fact_checkpoint_fingerprint", sa.String(length=71), nullable=False),
        sa.Column("checkpoint_json", sa.LargeBinary(), nullable=False),
        sa.Column("checkpoint_sha256", sa.String(length=64), nullable=False),
        sa.Column("state_revision", sa.Integer(), nullable=False),
        sa.Column("updated_at_utc", sa.String(length=32), nullable=False),
        _stored_at(),
        sa.PrimaryKeyConstraint(
            "data_plane",
            "factory_id",
            "planning_scope_id",
            "authority_id",
            "stream_id",
            "stream_version",
            name="pk_replan_projection_checkpoints",
        ),
        _simulation_check("ck_replan_projection_checkpoints_plane"),
        sa.CheckConstraint(
            "last_applied_position >= 1",
            name="ck_replan_projection_checkpoints_position",
        ),
        sa.CheckConstraint(
            "state_revision >= 0",
            name="ck_replan_projection_checkpoints_revision",
        ),
        sa.CheckConstraint(
            "length(prefix_fingerprint) = 71",
            name="ck_replan_projection_checkpoints_prefix",
        ),
        sa.CheckConstraint(
            "length(fact_checkpoint_fingerprint) = 71",
            name="ck_replan_projection_checkpoints_fact_fingerprint",
        ),
        sa.CheckConstraint(
            "length(checkpoint_sha256) = 64",
            name="ck_replan_projection_checkpoints_sha256",
        ),
    )

    op.create_table(
        "replan_requests",
        sa.Column("data_plane", sa.String(length=16), nullable=False),
        sa.Column("request_id", sa.String(length=256), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=71), nullable=False),
        sa.Column("environment", sa.String(length=32), nullable=False),
        sa.Column("factory_id", sa.String(length=256), nullable=False),
        sa.Column("planning_scope_id", sa.String(length=256), nullable=False),
        sa.Column("authority_id", sa.String(length=256), nullable=False),
        sa.Column("stream_id", sa.String(length=256), nullable=False),
        sa.Column("stream_version", sa.String(length=64), nullable=False),
        sa.Column("from_position", sa.Integer(), nullable=False),
        sa.Column("through_position", sa.Integer(), nullable=False),
        sa.Column("stream_fingerprint", sa.String(length=71), nullable=False),
        sa.Column("fact_checkpoint_version", sa.String(length=128), nullable=False),
        sa.Column("fact_checkpoint_id", sa.String(length=256), nullable=False),
        sa.Column("fact_checkpoint_fingerprint", sa.String(length=71), nullable=False),
        sa.Column("base_schedule_version_id", sa.String(length=256), nullable=False),
        sa.Column("requested_at_utc", sa.String(length=32), nullable=False),
        sa.Column("correlation_id", sa.String(length=256), nullable=False),
        sa.Column("document_json", sa.LargeBinary(), nullable=False),
        sa.Column("document_sha256", sa.String(length=64), nullable=False),
        _stored_at(),
        sa.PrimaryKeyConstraint("data_plane", "request_id", name="pk_replan_requests"),
        sa.UniqueConstraint(
            "data_plane",
            "request_fingerprint",
            name="uq_replan_requests_fingerprint",
        ),
        _simulation_check("ck_replan_requests_plane"),
        sa.CheckConstraint(
            "from_position >= 1 AND through_position >= from_position",
            name="ck_replan_requests_position_range",
        ),
        sa.CheckConstraint(
            "length(request_fingerprint) = 71",
            name="ck_replan_requests_fingerprint",
        ),
        sa.CheckConstraint(
            "length(stream_fingerprint) = 71",
            name="ck_replan_requests_stream_fingerprint",
        ),
        sa.CheckConstraint(
            "length(fact_checkpoint_fingerprint) = 71",
            name="ck_replan_requests_fact_fingerprint",
        ),
        sa.CheckConstraint(
            "length(document_sha256) = 64",
            name="ck_replan_requests_document_sha256",
        ),
    )
    op.create_index(
        "ix_replan_requests_scope_requested",
        "replan_requests",
        ["data_plane", "factory_id", "planning_scope_id", "requested_at_utc"],
    )

    op.create_table(
        "replan_request_events",
        sa.Column("data_plane", sa.String(length=16), nullable=False),
        sa.Column("request_id", sa.String(length=256), nullable=False),
        sa.Column("event_ordinal", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.String(length=256), nullable=False),
        sa.Column("event_fingerprint", sa.String(length=71), nullable=False),
        sa.Column("source_position", sa.Integer(), nullable=False),
        _stored_at(),
        sa.PrimaryKeyConstraint(
            "data_plane",
            "request_id",
            "event_ordinal",
            name="pk_replan_request_events",
        ),
        sa.UniqueConstraint(
            "data_plane",
            "request_id",
            "event_id",
            name="uq_replan_request_events_event",
        ),
        sa.ForeignKeyConstraint(
            ["data_plane", "request_id"],
            ["replan_requests.data_plane", "replan_requests.request_id"],
            name="fk_replan_request_events_request",
        ),
        sa.ForeignKeyConstraint(
            ["data_plane", "event_id"],
            ["execution_event_ledger.data_plane", "execution_event_ledger.event_id"],
            name="fk_replan_request_events_event",
        ),
        _simulation_check("ck_replan_request_events_plane"),
        sa.CheckConstraint(
            "event_ordinal >= 0", name="ck_replan_request_events_ordinal"
        ),
        sa.CheckConstraint(
            "source_position >= 1", name="ck_replan_request_events_position"
        ),
    )

    op.create_table(
        "replan_attempts",
        sa.Column("data_plane", sa.String(length=16), nullable=False),
        sa.Column("attempt_id", sa.String(length=256), nullable=False),
        sa.Column("attempt_fingerprint", sa.String(length=71), nullable=False),
        sa.Column("request_id", sa.String(length=256), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=71), nullable=False),
        sa.Column("planning_run_id", sa.String(length=256), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("idempotency_scope", sa.String(length=512), nullable=False),
        sa.Column("idempotency_key_reference", sa.String(length=71), nullable=False),
        sa.Column("correlation_id", sa.String(length=256), nullable=False),
        sa.Column("created_at_utc", sa.String(length=32), nullable=False),
        sa.Column("record_json", sa.LargeBinary(), nullable=False),
        sa.Column("record_sha256", sa.String(length=64), nullable=False),
        _stored_at(),
        sa.PrimaryKeyConstraint("data_plane", "attempt_id", name="pk_replan_attempts"),
        sa.UniqueConstraint(
            "data_plane",
            "request_id",
            "attempt_number",
            name="uq_replan_attempts_request_number",
        ),
        sa.UniqueConstraint(
            "data_plane", "planning_run_id", name="uq_replan_attempts_planning_run"
        ),
        sa.UniqueConstraint(
            "data_plane",
            "idempotency_scope",
            "idempotency_key_reference",
            name="uq_replan_attempts_idempotency",
        ),
        sa.ForeignKeyConstraint(
            ["data_plane", "request_id"],
            ["replan_requests.data_plane", "replan_requests.request_id"],
            name="fk_replan_attempts_request",
        ),
        _simulation_check("ck_replan_attempts_plane"),
        sa.CheckConstraint("attempt_number >= 1", name="ck_replan_attempts_number"),
        sa.CheckConstraint(
            "length(attempt_fingerprint) = 71",
            name="ck_replan_attempts_fingerprint",
        ),
        sa.CheckConstraint(
            "length(record_sha256) = 64", name="ck_replan_attempts_sha256"
        ),
    )

    op.create_table(
        "replan_results",
        sa.Column("data_plane", sa.String(length=16), nullable=False),
        sa.Column("result_id", sa.String(length=256), nullable=False),
        sa.Column("result_fingerprint", sa.String(length=71), nullable=False),
        sa.Column("attempt_id", sa.String(length=256), nullable=False),
        sa.Column("request_id", sa.String(length=256), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=71), nullable=False),
        sa.Column("planning_run_id", sa.String(length=256), nullable=False),
        sa.Column("planning_run_terminal_state", sa.String(length=32), nullable=False),
        sa.Column("solver_report_id", sa.String(length=256)),
        sa.Column("solver_report_fingerprint", sa.String(length=71)),
        sa.Column("validation_report_id", sa.String(length=256)),
        sa.Column("validation_report_fingerprint", sa.String(length=71)),
        sa.Column("new_schedule_version_id", sa.String(length=256)),
        sa.Column("new_schedule_content_fingerprint", sa.String(length=71)),
        sa.Column("change_report_id", sa.String(length=256)),
        sa.Column("change_report_fingerprint", sa.String(length=71)),
        sa.Column("correlation_id", sa.String(length=256), nullable=False),
        sa.Column("finished_at_utc", sa.String(length=32), nullable=False),
        sa.Column("record_json", sa.LargeBinary(), nullable=False),
        sa.Column("record_sha256", sa.String(length=64), nullable=False),
        _stored_at(),
        sa.PrimaryKeyConstraint("data_plane", "result_id", name="pk_replan_results"),
        sa.UniqueConstraint(
            "data_plane", "attempt_id", name="uq_replan_results_attempt"
        ),
        sa.ForeignKeyConstraint(
            ["data_plane", "attempt_id"],
            ["replan_attempts.data_plane", "replan_attempts.attempt_id"],
            name="fk_replan_results_attempt",
        ),
        sa.ForeignKeyConstraint(
            ["data_plane", "request_id"],
            ["replan_requests.data_plane", "replan_requests.request_id"],
            name="fk_replan_results_request",
        ),
        _simulation_check("ck_replan_results_plane"),
        sa.CheckConstraint(
            "planning_run_terminal_state IN ('COMPLETED', 'DATA_REJECTED', "
            "'MODEL_INVALID', 'INFEASIBLE', 'NO_SOLUTION_WITHIN_LIMIT', "
            "'VALIDATION_FAILED', 'CANCELLED', 'FAILED')",
            name="ck_replan_results_terminal_state",
        ),
        sa.CheckConstraint(
            "((solver_report_id IS NULL AND solver_report_fingerprint IS NULL) OR "
            "(solver_report_id IS NOT NULL AND solver_report_fingerprint IS NOT NULL))",
            name="ck_replan_results_solver_pair",
        ),
        sa.CheckConstraint(
            "((validation_report_id IS NULL AND validation_report_fingerprint IS NULL) "
            "OR (validation_report_id IS NOT NULL AND "
            "validation_report_fingerprint IS NOT NULL))",
            name="ck_replan_results_validation_pair",
        ),
        sa.CheckConstraint(
            "((new_schedule_version_id IS NULL AND "
            "new_schedule_content_fingerprint IS NULL) OR "
            "(new_schedule_version_id IS NOT NULL AND "
            "new_schedule_content_fingerprint IS NOT NULL))",
            name="ck_replan_results_schedule_pair",
        ),
        sa.CheckConstraint(
            "((change_report_id IS NULL AND change_report_fingerprint IS NULL) OR "
            "(change_report_id IS NOT NULL AND change_report_fingerprint IS NOT NULL))",
            name="ck_replan_results_change_pair",
        ),
        sa.CheckConstraint(
            "((planning_run_terminal_state = 'COMPLETED' AND "
            "solver_report_id IS NOT NULL AND validation_report_id IS NOT NULL AND "
            "new_schedule_version_id IS NOT NULL AND change_report_id IS NOT NULL) OR "
            "(planning_run_terminal_state <> 'COMPLETED' AND "
            "new_schedule_version_id IS NULL AND change_report_id IS NULL))",
            name="ck_replan_results_completion_refs",
        ),
        sa.CheckConstraint(
            "length(result_fingerprint) = 71",
            name="ck_replan_results_fingerprint",
        ),
        sa.CheckConstraint(
            "length(record_sha256) = 64", name="ck_replan_results_sha256"
        ),
    )
    op.create_index(
        "ix_replan_results_request_finished",
        "replan_results",
        ["data_plane", "request_id", "finished_at_utc"],
    )

    op.create_table(
        "replan_audit_records",
        sa.Column("data_plane", sa.String(length=16), nullable=False),
        sa.Column("audit_record_id", sa.String(length=256), nullable=False),
        sa.Column("audit_fingerprint", sa.String(length=71), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("aggregate_type", sa.String(length=64), nullable=False),
        sa.Column("aggregate_id", sa.String(length=256), nullable=False),
        sa.Column("correlation_id", sa.String(length=256), nullable=False),
        sa.Column("idempotency_scope", sa.String(length=512), nullable=False),
        sa.Column("idempotency_key_reference", sa.String(length=71), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=71)),
        sa.Column("occurred_at_utc", sa.String(length=32), nullable=False),
        sa.Column("record_json", sa.LargeBinary(), nullable=False),
        sa.Column("record_sha256", sa.String(length=64), nullable=False),
        _stored_at(),
        sa.PrimaryKeyConstraint(
            "data_plane", "audit_record_id", name="pk_replan_audit_records"
        ),
        sa.UniqueConstraint(
            "data_plane",
            "idempotency_scope",
            "idempotency_key_reference",
            name="uq_replan_audit_records_idempotency",
        ),
        _simulation_check("ck_replan_audit_records_plane"),
        sa.CheckConstraint(
            "action IN ('EXECUTION_EVENT_APPENDED', "
            "'PROJECTION_CHECKPOINT_COMMITTED', 'REPLAN_REQUEST_APPENDED', "
            "'REPLAN_ATTEMPT_LINKED', 'REPLAN_RESULT_APPENDED')",
            name="ck_replan_audit_records_action",
        ),
        sa.CheckConstraint(
            "length(audit_fingerprint) = 71",
            name="ck_replan_audit_records_fingerprint",
        ),
        sa.CheckConstraint(
            "length(record_sha256) = 64", name="ck_replan_audit_records_sha256"
        ),
    )
    op.create_index(
        "ix_replan_audit_records_aggregate_time",
        "replan_audit_records",
        ["data_plane", "aggregate_type", "aggregate_id", "occurred_at_utc"],
    )
    op.create_index(
        "ix_replan_audit_records_correlation",
        "replan_audit_records",
        ["data_plane", "correlation_id"],
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
        "CREATE TRIGGER trg_replan_projection_checkpoints_immutable_scope "
        "BEFORE UPDATE OF data_plane, factory_id, planning_scope_id, authority_id, "
        "stream_id, stream_version ON replan_projection_checkpoints "
        "BEGIN SELECT RAISE(ABORT, 'projection checkpoint scope is immutable'); END"
    )
    op.execute(
        "CREATE TRIGGER trg_replan_projection_checkpoints_no_delete BEFORE DELETE ON "
        "replan_projection_checkpoints BEGIN SELECT RAISE(ABORT, "
        "'projection checkpoints cannot be deleted'); END"
    )


def _create_postgresql_guards() -> None:
    op.execute(
        "CREATE FUNCTION reject_replan_append_only_mutation() RETURNS trigger "
        "LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION '% is append-only', "
        "TG_TABLE_NAME; END; $$"
    )
    for table in _APPEND_ONLY_TABLES:
        op.execute(
            f"CREATE TRIGGER trg_{table}_no_update BEFORE UPDATE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION reject_replan_append_only_mutation()"
        )
        op.execute(
            f"CREATE TRIGGER trg_{table}_no_delete BEFORE DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION reject_replan_append_only_mutation()"
        )
    op.execute(
        "CREATE FUNCTION guard_replan_checkpoint_immutable_scope() RETURNS trigger "
        "LANGUAGE plpgsql AS $$ BEGIN IF ROW(NEW.data_plane, NEW.factory_id, "
        "NEW.planning_scope_id, NEW.authority_id, NEW.stream_id, "
        "NEW.stream_version) IS DISTINCT FROM ROW(OLD.data_plane, OLD.factory_id, "
        "OLD.planning_scope_id, OLD.authority_id, OLD.stream_id, "
        "OLD.stream_version) THEN RAISE EXCEPTION "
        "'projection checkpoint scope is immutable'; END IF; RETURN NEW; END; $$"
    )
    op.execute(
        "CREATE TRIGGER trg_replan_projection_checkpoints_immutable_scope BEFORE "
        "UPDATE ON replan_projection_checkpoints FOR EACH ROW EXECUTE FUNCTION "
        "guard_replan_checkpoint_immutable_scope()"
    )
    op.execute(
        "CREATE TRIGGER trg_replan_projection_checkpoints_no_delete BEFORE DELETE ON "
        "replan_projection_checkpoints FOR EACH ROW EXECUTE FUNCTION "
        "reject_replan_append_only_mutation()"
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
        op.execute("DROP TRIGGER trg_replan_projection_checkpoints_no_delete")
        op.execute("DROP TRIGGER trg_replan_projection_checkpoints_immutable_scope")
    elif dialect == "postgresql":
        for table in _APPEND_ONLY_TABLES:
            op.execute(f"DROP TRIGGER trg_{table}_no_delete ON {table}")
            op.execute(f"DROP TRIGGER trg_{table}_no_update ON {table}")
        op.execute(
            "DROP TRIGGER trg_replan_projection_checkpoints_no_delete ON "
            "replan_projection_checkpoints"
        )
        op.execute(
            "DROP TRIGGER trg_replan_projection_checkpoints_immutable_scope ON "
            "replan_projection_checkpoints"
        )
        op.execute("DROP FUNCTION guard_replan_checkpoint_immutable_scope()")
        op.execute("DROP FUNCTION reject_replan_append_only_mutation()")

    op.drop_index(
        "ix_replan_audit_records_correlation", table_name="replan_audit_records"
    )
    op.drop_index(
        "ix_replan_audit_records_aggregate_time",
        table_name="replan_audit_records",
    )
    op.drop_table("replan_audit_records")
    op.drop_index("ix_replan_results_request_finished", table_name="replan_results")
    op.drop_table("replan_results")
    op.drop_table("replan_attempts")
    op.drop_table("replan_request_events")
    op.drop_index("ix_replan_requests_scope_requested", table_name="replan_requests")
    op.drop_table("replan_requests")
    op.drop_table("replan_projection_checkpoints")
    op.drop_index(
        "ix_execution_event_ledger_correlation",
        table_name="execution_event_ledger",
    )
    op.drop_index(
        "ix_execution_event_ledger_scope_position",
        table_name="execution_event_ledger",
    )
    op.drop_table("execution_event_ledger")
