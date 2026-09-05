"""Create immutable P8 Solver Worker bindings and result checkpoints.

Revision ID: 0008_planning_run_solver_worker
Revises: 0007_planning_run_orchestration
Create Date: 2026-09-05

The checkpoint closes the crash window between one Solver/Validator execution
and the existing PlanningRun/ScheduleVersion application boundaries.  It is
internal evidence, not a public PlanningRun artifact or a publication result.
Downgrade is destructive for pending Worker recovery and therefore requires a
stopped Worker plus an operator-confirmed absence of unreconciled checkpoints.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0008_planning_run_solver_worker"
down_revision: str | None = "0007_planning_run_orchestration"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_BINDING_TABLE = "planning_run_worker_jobs"
_RESULT_TABLE = "planning_run_worker_results"


def upgrade() -> None:
    op.create_table(
        _BINDING_TABLE,
        sa.Column("job_id", sa.String(length=64), nullable=False),
        sa.Column("planning_run_id", sa.String(length=256), nullable=False),
        sa.Column("attempt_id", sa.String(length=256), nullable=False),
        sa.Column("work_item_id", sa.String(length=256), nullable=False),
        sa.Column("data_plane", sa.String(length=16), nullable=False),
        sa.Column("work_item_fingerprint", sa.String(length=71), nullable=False),
        sa.Column(
            "runtime_resolution_fingerprint", sa.String(length=71), nullable=False
        ),
        sa.Column("created_at_utc", sa.String(length=32), nullable=False),
        sa.Column(
            "stored_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.PrimaryKeyConstraint("job_id", name="pk_planning_run_worker_jobs"),
        sa.UniqueConstraint("attempt_id", name="uq_planning_run_worker_job_attempt"),
        sa.UniqueConstraint(
            "work_item_id", name="uq_planning_run_worker_job_work_item"
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["engineering_job_records.job_id"],
            name="fk_planning_run_worker_job_record",
        ),
        sa.ForeignKeyConstraint(
            ["planning_run_id"],
            ["planning_runs.planning_run_id"],
            name="fk_planning_run_worker_job_run",
        ),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["planning_run_attempts.attempt_id"],
            name="fk_planning_run_worker_job_attempt",
        ),
        sa.ForeignKeyConstraint(
            ["work_item_id"],
            ["planning_run_work_items.work_item_id"],
            name="fk_planning_run_worker_job_work_item",
        ),
        sa.CheckConstraint(
            "data_plane IN ('SIMULATION', 'PRODUCTION')",
            name="ck_planning_run_worker_job_plane",
        ),
        sa.CheckConstraint(
            "length(work_item_fingerprint) = 71",
            name="ck_planning_run_worker_job_work_fingerprint",
        ),
        sa.CheckConstraint(
            "length(runtime_resolution_fingerprint) = 71",
            name="ck_planning_run_worker_job_runtime_fingerprint",
        ),
    )
    op.create_index(
        "ix_planning_run_worker_jobs_run",
        _BINDING_TABLE,
        ["data_plane", "planning_run_id", "attempt_id"],
    )

    op.create_table(
        _RESULT_TABLE,
        sa.Column("result_id", sa.String(length=256), nullable=False),
        sa.Column("job_id", sa.String(length=64), nullable=False),
        sa.Column("planning_run_id", sa.String(length=256), nullable=False),
        sa.Column("attempt_id", sa.String(length=256), nullable=False),
        sa.Column("work_item_id", sa.String(length=256), nullable=False),
        sa.Column("data_plane", sa.String(length=16), nullable=False),
        sa.Column("outcome_state", sa.String(length=32), nullable=False),
        sa.Column("work_item_fingerprint", sa.String(length=71), nullable=False),
        sa.Column(
            "runtime_resolution_fingerprint", sa.String(length=71), nullable=False
        ),
        sa.Column("result_fingerprint", sa.String(length=71), nullable=False),
        sa.Column("result_json", sa.LargeBinary(), nullable=False),
        sa.Column("result_sha256", sa.String(length=64), nullable=False),
        sa.Column("created_at_utc", sa.String(length=32), nullable=False),
        sa.Column(
            "stored_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.PrimaryKeyConstraint("result_id", name="pk_planning_run_worker_results"),
        sa.UniqueConstraint("job_id", name="uq_planning_run_worker_result_job"),
        sa.UniqueConstraint("attempt_id", name="uq_planning_run_worker_result_attempt"),
        sa.UniqueConstraint(
            "work_item_id", name="uq_planning_run_worker_result_work_item"
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["engineering_job_records.job_id"],
            name="fk_planning_run_worker_result_job",
        ),
        sa.ForeignKeyConstraint(
            ["planning_run_id"],
            ["planning_runs.planning_run_id"],
            name="fk_planning_run_worker_result_run",
        ),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["planning_run_attempts.attempt_id"],
            name="fk_planning_run_worker_result_attempt",
        ),
        sa.ForeignKeyConstraint(
            ["work_item_id"],
            ["planning_run_work_items.work_item_id"],
            name="fk_planning_run_worker_result_work_item",
        ),
        sa.CheckConstraint(
            "data_plane IN ('SIMULATION', 'PRODUCTION')",
            name="ck_planning_run_worker_result_plane",
        ),
        sa.CheckConstraint(
            "outcome_state IN ('COMPLETED','MODEL_INVALID','INFEASIBLE',"
            "'NO_SOLUTION_WITHIN_LIMIT','VALIDATION_FAILED','CANCELLED','FAILED')",
            name="ck_planning_run_worker_result_outcome",
        ),
        sa.CheckConstraint(
            "length(work_item_fingerprint) = 71",
            name="ck_planning_run_worker_result_work_fingerprint",
        ),
        sa.CheckConstraint(
            "length(runtime_resolution_fingerprint) = 71",
            name="ck_planning_run_worker_result_runtime_fingerprint",
        ),
        sa.CheckConstraint(
            "length(result_fingerprint) = 71",
            name="ck_planning_run_worker_result_fingerprint",
        ),
        sa.CheckConstraint(
            "length(result_sha256) = 64",
            name="ck_planning_run_worker_result_sha256",
        ),
    )
    op.create_index(
        "ix_planning_run_worker_results_run",
        _RESULT_TABLE,
        ["data_plane", "planning_run_id", "attempt_id"],
    )

    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        for table in (_BINDING_TABLE, _RESULT_TABLE):
            op.execute(
                f"CREATE TRIGGER trg_{table}_no_update BEFORE UPDATE ON {table} "
                f"BEGIN SELECT RAISE(ABORT, '{table} is append-only'); END"
            )
            op.execute(
                f"CREATE TRIGGER trg_{table}_no_delete BEFORE DELETE ON {table} "
                f"BEGIN SELECT RAISE(ABORT, '{table} is append-only'); END"
            )
    elif dialect == "postgresql":
        op.execute(
            "CREATE FUNCTION reject_planning_run_worker_result_mutation() "
            "RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION "
            "'planning_run_worker_results is append-only'; END; $$"
        )
        for table in (_BINDING_TABLE, _RESULT_TABLE):
            for action in ("update", "delete"):
                op.execute(
                    f"CREATE TRIGGER trg_{table}_no_{action} BEFORE {action.upper()} "
                    f"ON {table} FOR EACH ROW EXECUTE FUNCTION "
                    "reject_planning_run_worker_result_mutation()"
                )


def downgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        for table in (_RESULT_TABLE, _BINDING_TABLE):
            op.execute(f"DROP TRIGGER trg_{table}_no_delete")
            op.execute(f"DROP TRIGGER trg_{table}_no_update")
    elif dialect == "postgresql":
        for table in (_RESULT_TABLE, _BINDING_TABLE):
            op.execute(f"DROP TRIGGER trg_{table}_no_delete ON {table}")
            op.execute(f"DROP TRIGGER trg_{table}_no_update ON {table}")
        op.execute("DROP FUNCTION reject_planning_run_worker_result_mutation()")
    op.drop_index("ix_planning_run_worker_results_run", table_name=_RESULT_TABLE)
    op.drop_table(_RESULT_TABLE)
    op.drop_index("ix_planning_run_worker_jobs_run", table_name=_BINDING_TABLE)
    op.drop_table(_BINDING_TABLE)
    op.execute(
        "DELETE FROM engineering_job_records "
        "WHERE job_kind = 'P8_PLANNING_RUN_SOLVER'"
    )
