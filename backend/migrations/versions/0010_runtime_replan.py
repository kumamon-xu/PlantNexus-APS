"""Allow explicit ReplanRequest successors of one canonical ingress.

Revision ID: 0010_runtime_replan
Revises: 0009_host_authorization_audit
"""

from alembic import op
import sqlalchemy as sa

revision: str = "0010_runtime_replan"
down_revision: str | None = "0009_host_authorization_audit"
branch_labels = None
depends_on = None


def _sqlite_run_guards() -> list[str]:
    if op.get_bind().dialect.name != "sqlite":
        return []
    return list(
        op.get_bind()
        .execute(
            sa.text(
                "SELECT sql FROM sqlite_master WHERE type='trigger' AND tbl_name='planning_runs' ORDER BY name"
            )
        )
        .scalars()
    )


def upgrade() -> None:
    guards = _sqlite_run_guards()
    with op.batch_alter_table("planning_runs") as batch:
        batch.add_column(sa.Column("replan_request_id", sa.String(256), nullable=True))
        batch.drop_constraint("uq_planning_runs_ingress", type_="unique")
        batch.create_foreign_key(
            "fk_planning_runs_replan_request",
            "replan_requests",
            ["data_plane", "replan_request_id"],
            ["data_plane", "request_id"],
        )
    for guard in guards:
        op.execute(guard)
    if op.get_bind().dialect.name == "sqlite":
        op.execute(
            "CREATE TRIGGER trg_runtime_replan_source_immutable BEFORE UPDATE ON planning_runs "
            "WHEN NEW.replan_request_id IS NOT OLD.replan_request_id "
            "BEGIN SELECT RAISE(ABORT, 'replan source is immutable'); END"
        )
    else:
        op.execute(
            "CREATE FUNCTION reject_runtime_replan_source_mutation() RETURNS trigger LANGUAGE plpgsql AS $$ "
            "BEGIN IF NEW.replan_request_id IS DISTINCT FROM OLD.replan_request_id THEN RAISE EXCEPTION "
            "'replan source is immutable'; END IF; RETURN NEW; END; $$"
        )
        op.execute(
            "CREATE TRIGGER trg_runtime_replan_source_immutable BEFORE UPDATE ON planning_runs "
            "FOR EACH ROW EXECUTE FUNCTION reject_runtime_replan_source_mutation()"
        )
    op.create_index(
        "uq_planning_runs_canonical_ingress",
        "planning_runs",
        ["ingress_id"],
        unique=True,
        sqlite_where=sa.text("replan_request_id IS NULL"),
        postgresql_where=sa.text("replan_request_id IS NULL"),
    )
    op.create_table(
        "runtime_replan_checkpoints",
        sa.Column("work_item_id", sa.String(256), primary_key=True),
        sa.Column("planning_run_id", sa.String(256), nullable=False),
        sa.Column("data_plane", sa.String(16), nullable=False),
        sa.Column("document_json", sa.LargeBinary(), nullable=False),
        sa.Column("document_sha256", sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(
            ["work_item_id"], ["planning_run_work_items.work_item_id"]
        ),
        sa.ForeignKeyConstraint(["planning_run_id"], ["planning_runs.planning_run_id"]),
        sa.CheckConstraint(
            "data_plane = 'SIMULATION'", name="ck_runtime_replan_checkpoint_plane"
        ),
    )
    if op.get_bind().dialect.name == "sqlite":
        for action in ("update", "delete"):
            op.execute(
                f"CREATE TRIGGER trg_runtime_replan_checkpoint_no_{action} "
                f"BEFORE {action.upper()} ON runtime_replan_checkpoints "
                "BEGIN SELECT RAISE(ABORT, 'replan checkpoint is append-only'); END"
            )
    elif op.get_bind().dialect.name == "postgresql":
        op.execute(
            "CREATE FUNCTION reject_runtime_replan_checkpoint_mutation() "
            "RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION "
            "'replan checkpoint is append-only'; END; $$"
        )
        for action in ("update", "delete"):
            op.execute(
                f"CREATE TRIGGER trg_runtime_replan_checkpoint_no_{action} "
                f"BEFORE {action.upper()} ON runtime_replan_checkpoints "
                "FOR EACH ROW EXECUTE FUNCTION reject_runtime_replan_checkpoint_mutation()"
            )


def downgrade() -> None:
    if op.get_bind().scalar(
        sa.text(
            "SELECT count(*) FROM planning_runs WHERE replan_request_id IS NOT NULL"
        )
    ):
        raise RuntimeError(
            "Runtime replan history exists; downgrade would lose lineage"
        )
    if op.get_bind().dialect.name == "sqlite":
        op.execute("DROP TRIGGER trg_runtime_replan_source_immutable")
    else:
        op.execute("DROP TRIGGER trg_runtime_replan_source_immutable ON planning_runs")
        op.execute("DROP FUNCTION reject_runtime_replan_source_mutation()")
    guards = _sqlite_run_guards()
    op.drop_table("runtime_replan_checkpoints")
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP FUNCTION reject_runtime_replan_checkpoint_mutation()")
    op.drop_index("uq_planning_runs_canonical_ingress", table_name="planning_runs")
    with op.batch_alter_table("planning_runs") as batch:
        batch.drop_constraint("fk_planning_runs_replan_request", type_="foreignkey")
        batch.drop_column("replan_request_id")
        batch.create_unique_constraint("uq_planning_runs_ingress", ["ingress_id"])
    for guard in guards:
        op.execute(guard)
