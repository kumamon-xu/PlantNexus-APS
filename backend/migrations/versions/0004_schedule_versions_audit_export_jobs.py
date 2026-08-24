"""Create P3 ScheduleVersion, audit, publication, and ExportJob storage.

Revision ID: 0004_schedule_versions_audit_export_jobs
Revises: 0003_planning_snapshots
Create Date: 2026-08-24

The new tables provide storage primitives only.  They do not authorize or
execute approval, publication, or export business actions.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_schedule_versions_audit_export_jobs"
down_revision: str | None = "0003_planning_snapshots"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_tables() -> None:
    op.create_table(
        "schedule_versions",
        sa.Column("data_plane", sa.String(length=16), nullable=False),
        sa.Column("schedule_version_id", sa.String(length=256), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("environment", sa.String(length=32), nullable=False),
        sa.Column("synthetic", sa.Boolean(), nullable=False),
        sa.Column("parent_schedule_version_id", sa.String(length=256)),
        sa.Column("content_fingerprint", sa.String(length=71), nullable=False),
        sa.Column("immutable_fingerprint", sa.String(length=71), nullable=False),
        sa.Column("content_json", sa.LargeBinary(), nullable=False),
        sa.Column("creation_json", sa.LargeBinary(), nullable=False),
        sa.Column("document_json", sa.LargeBinary(), nullable=False),
        sa.Column("document_sha256", sa.String(length=64), nullable=False),
        sa.Column("state_revision", sa.Integer(), nullable=False),
        sa.Column("created_at_utc", sa.String(length=32), nullable=False),
        sa.Column(
            "stored_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.PrimaryKeyConstraint(
            "data_plane",
            "schedule_version_id",
            name="pk_schedule_versions",
        ),
        sa.ForeignKeyConstraint(
            ["data_plane", "parent_schedule_version_id"],
            ["schedule_versions.data_plane", "schedule_versions.schedule_version_id"],
            name="fk_schedule_versions_parent",
        ),
        sa.CheckConstraint(
            "data_plane IN ('SIMULATION', 'PRODUCTION')",
            name="ck_schedule_versions_data_plane",
        ),
        sa.CheckConstraint(
            "state IN ('DRAFT', 'READY_FOR_REVIEW', 'APPROVED', 'PUBLISHED', "
            "'SUPERSEDED', 'REJECTED')",
            name="ck_schedule_versions_state",
        ),
        sa.CheckConstraint("revision >= 1", name="ck_schedule_versions_revision"),
        sa.CheckConstraint(
            "state_revision >= 0",
            name="ck_schedule_versions_state_revision",
        ),
        sa.CheckConstraint(
            "length(content_fingerprint) = 71",
            name="ck_schedule_versions_content_fingerprint",
        ),
        sa.CheckConstraint(
            "length(immutable_fingerprint) = 71",
            name="ck_schedule_versions_immutable_fingerprint",
        ),
        sa.CheckConstraint(
            "length(document_sha256) = 64",
            name="ck_schedule_versions_document_sha256",
        ),
    )
    op.create_index(
        "ix_schedule_versions_plane_state_created",
        "schedule_versions",
        ["data_plane", "state", "created_at_utc"],
    )
    op.create_index(
        "ix_schedule_versions_plane_parent_revision",
        "schedule_versions",
        ["data_plane", "parent_schedule_version_id", "revision"],
    )

    op.create_table(
        "audit_events",
        sa.Column("data_plane", sa.String(length=16), nullable=False),
        sa.Column("audit_event_id", sa.String(length=256), nullable=False),
        sa.Column("environment", sa.String(length=32), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("aggregate_type", sa.String(length=32), nullable=False),
        sa.Column("aggregate_id", sa.String(length=256), nullable=False),
        sa.Column("correlation_id", sa.String(length=256), nullable=False),
        sa.Column("parent_audit_event_id", sa.String(length=256)),
        sa.Column("occurred_at_utc", sa.String(length=32), nullable=False),
        sa.Column("idempotency_scope", sa.String(length=512)),
        sa.Column("idempotency_key_reference", sa.String(length=71)),
        sa.Column("request_fingerprint", sa.String(length=71)),
        sa.Column("document_json", sa.LargeBinary(), nullable=False),
        sa.Column("document_sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "stored_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.PrimaryKeyConstraint("data_plane", "audit_event_id", name="pk_audit_events"),
        sa.ForeignKeyConstraint(
            ["data_plane", "parent_audit_event_id"],
            ["audit_events.data_plane", "audit_events.audit_event_id"],
            name="fk_audit_events_parent",
        ),
        sa.UniqueConstraint(
            "data_plane",
            "idempotency_scope",
            "idempotency_key_reference",
            name="uq_audit_events_plane_idempotency",
        ),
        sa.CheckConstraint(
            "data_plane IN ('SIMULATION', 'PRODUCTION')",
            name="ck_audit_events_data_plane",
        ),
        sa.CheckConstraint(
            "length(document_sha256) = 64",
            name="ck_audit_events_document_sha256",
        ),
    )
    op.create_index(
        "ix_audit_events_plane_aggregate_time",
        "audit_events",
        ["data_plane", "aggregate_type", "aggregate_id", "occurred_at_utc"],
    )
    op.create_index(
        "ix_audit_events_plane_correlation",
        "audit_events",
        ["data_plane", "correlation_id"],
    )

    op.create_table(
        "publication_results",
        sa.Column("data_plane", sa.String(length=16), nullable=False),
        sa.Column("publication_id", sa.String(length=256), nullable=False),
        sa.Column("target", sa.String(length=64), nullable=False),
        sa.Column("source_schedule_version_id", sa.String(length=256), nullable=False),
        sa.Column(
            "published_schedule_version_id", sa.String(length=256), nullable=False
        ),
        sa.Column("previous_current_version_id", sa.String(length=256)),
        sa.Column("idempotency_scope", sa.String(length=512), nullable=False),
        sa.Column("idempotency_key_reference", sa.String(length=71), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=71), nullable=False),
        sa.Column("result_fingerprint", sa.String(length=71), nullable=False),
        sa.Column("published_at_utc", sa.String(length=32), nullable=False),
        sa.Column("document_json", sa.LargeBinary(), nullable=False),
        sa.Column("document_sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "stored_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.PrimaryKeyConstraint(
            "data_plane", "publication_id", name="pk_publication_results"
        ),
        sa.UniqueConstraint(
            "data_plane",
            "idempotency_scope",
            "idempotency_key_reference",
            name="uq_publication_results_plane_idempotency",
        ),
        sa.ForeignKeyConstraint(
            ["data_plane", "source_schedule_version_id"],
            ["schedule_versions.data_plane", "schedule_versions.schedule_version_id"],
            name="fk_publication_results_source_version",
        ),
        sa.ForeignKeyConstraint(
            ["data_plane", "published_schedule_version_id"],
            ["schedule_versions.data_plane", "schedule_versions.schedule_version_id"],
            name="fk_publication_results_published_version",
        ),
        sa.ForeignKeyConstraint(
            ["data_plane", "previous_current_version_id"],
            ["schedule_versions.data_plane", "schedule_versions.schedule_version_id"],
            name="fk_publication_results_previous_version",
        ),
        sa.CheckConstraint(
            "data_plane = 'SIMULATION'",
            name="ck_publication_results_data_plane",
        ),
        sa.CheckConstraint(
            "target = 'SIMULATION_INTERNAL'",
            name="ck_publication_results_target",
        ),
    )
    op.create_index(
        "ix_publication_results_plane_published",
        "publication_results",
        ["data_plane", "published_schedule_version_id", "published_at_utc"],
    )

    op.create_table(
        "publication_current_references",
        sa.Column("data_plane", sa.String(length=16), nullable=False),
        sa.Column("target", sa.String(length=64), nullable=False),
        sa.Column("schedule_version_id", sa.String(length=256), nullable=False),
        sa.Column("content_fingerprint", sa.String(length=71), nullable=False),
        sa.Column("publication_id", sa.String(length=256), nullable=False),
        sa.Column("reference_revision", sa.Integer(), nullable=False),
        sa.Column("updated_at_utc", sa.String(length=32), nullable=False),
        sa.PrimaryKeyConstraint(
            "data_plane", "target", name="pk_publication_current_references"
        ),
        sa.ForeignKeyConstraint(
            ["data_plane", "schedule_version_id"],
            ["schedule_versions.data_plane", "schedule_versions.schedule_version_id"],
            name="fk_publication_current_schedule_version",
        ),
        sa.ForeignKeyConstraint(
            ["data_plane", "publication_id"],
            ["publication_results.data_plane", "publication_results.publication_id"],
            name="fk_publication_current_result",
        ),
        sa.CheckConstraint(
            "data_plane = 'SIMULATION'",
            name="ck_publication_current_data_plane",
        ),
        sa.CheckConstraint(
            "target = 'SIMULATION_INTERNAL'",
            name="ck_publication_current_target",
        ),
        sa.CheckConstraint(
            "reference_revision >= 0",
            name="ck_publication_current_revision",
        ),
    )

    op.create_table(
        "export_jobs",
        sa.Column("data_plane", sa.String(length=16), nullable=False),
        sa.Column("export_job_id", sa.String(length=256), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("environment", sa.String(length=32), nullable=False),
        sa.Column("schedule_version_id", sa.String(length=256), nullable=False),
        sa.Column("schedule_content_fingerprint", sa.String(length=71), nullable=False),
        sa.Column("target", sa.String(length=64), nullable=False),
        sa.Column("package_profile", sa.String(length=64), nullable=False),
        sa.Column("idempotency_scope", sa.String(length=512), nullable=False),
        sa.Column("idempotency_key_reference", sa.String(length=71), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=71), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("lease_reference", sa.String(length=71)),
        sa.Column("lease_expires_at_utc", sa.DateTime(timezone=True)),
        sa.Column("heartbeat_at_utc", sa.String(length=32)),
        sa.Column("job_fingerprint", sa.String(length=71), nullable=False),
        sa.Column("creation_json", sa.LargeBinary(), nullable=False),
        sa.Column("document_json", sa.LargeBinary(), nullable=False),
        sa.Column("document_sha256", sa.String(length=64), nullable=False),
        sa.Column("state_revision", sa.Integer(), nullable=False),
        sa.Column("updated_at_utc", sa.String(length=32), nullable=False),
        sa.Column(
            "stored_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.PrimaryKeyConstraint("data_plane", "export_job_id", name="pk_export_jobs"),
        sa.UniqueConstraint(
            "data_plane",
            "idempotency_scope",
            "idempotency_key_reference",
            name="uq_export_jobs_plane_idempotency",
        ),
        sa.ForeignKeyConstraint(
            ["data_plane", "schedule_version_id"],
            ["schedule_versions.data_plane", "schedule_versions.schedule_version_id"],
            name="fk_export_jobs_schedule_version",
        ),
        sa.CheckConstraint("data_plane = 'SIMULATION'", name="ck_export_jobs_plane"),
        sa.CheckConstraint(
            "state IN ('CREATED', 'EXPORTING', 'EXPORTED', 'EXPORT_FAILED', "
            "'CANCELLED')",
            name="ck_export_jobs_state",
        ),
        sa.CheckConstraint("attempt >= 0", name="ck_export_jobs_attempt"),
        sa.CheckConstraint("state_revision >= 0", name="ck_export_jobs_state_revision"),
        sa.CheckConstraint(
            "target = 'SIMULATION_INTERNAL'", name="ck_export_jobs_target"
        ),
        sa.CheckConstraint(
            "package_profile = 'p3-standard-export.v1'",
            name="ck_export_jobs_package_profile",
        ),
    )
    op.create_index(
        "ix_export_jobs_plane_state_updated",
        "export_jobs",
        ["data_plane", "state", "updated_at_utc"],
    )
    op.create_index(
        "ix_export_jobs_plane_lease",
        "export_jobs",
        ["data_plane", "state", "lease_expires_at_utc"],
    )


def _create_sqlite_guards() -> None:
    op.execute(
        "CREATE TRIGGER trg_schedule_versions_immutable_columns "
        "BEFORE UPDATE OF data_plane, schedule_version_id, revision, environment, "
        "synthetic, parent_schedule_version_id, content_fingerprint, "
        "immutable_fingerprint, content_json, creation_json, created_at_utc "
        "ON schedule_versions BEGIN SELECT RAISE(ABORT, "
        "'schedule_versions immutable content'); END"
    )
    op.execute(
        "CREATE TRIGGER trg_schedule_versions_no_delete BEFORE DELETE ON "
        "schedule_versions BEGIN SELECT RAISE(ABORT, "
        "'schedule_versions cannot be deleted'); END"
    )
    for table in ("audit_events", "publication_results"):
        op.execute(
            f"CREATE TRIGGER trg_{table}_no_update BEFORE UPDATE ON {table} "
            f"BEGIN SELECT RAISE(ABORT, '{table} is append-only'); END"
        )
        op.execute(
            f"CREATE TRIGGER trg_{table}_no_delete BEFORE DELETE ON {table} "
            f"BEGIN SELECT RAISE(ABORT, '{table} is append-only'); END"
        )
    op.execute(
        "CREATE TRIGGER trg_export_jobs_immutable_columns BEFORE UPDATE OF "
        "data_plane, export_job_id, environment, schedule_version_id, "
        "schedule_content_fingerprint, target, package_profile, "
        "idempotency_scope, idempotency_key_reference, request_fingerprint, "
        "creation_json ON export_jobs BEGIN SELECT RAISE(ABORT, "
        "'export_jobs immutable identity'); END"
    )
    op.execute(
        "CREATE TRIGGER trg_export_jobs_no_delete BEFORE DELETE ON export_jobs "
        "BEGIN SELECT RAISE(ABORT, 'export_jobs cannot be deleted'); END"
    )


def _create_postgresql_guards() -> None:
    op.execute(
        "CREATE FUNCTION reject_workspace_append_only_mutation() RETURNS trigger "
        "LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION '% is append-only', "
        "TG_TABLE_NAME; END; $$"
    )
    for table in ("audit_events", "publication_results"):
        op.execute(
            f"CREATE TRIGGER trg_{table}_no_update BEFORE UPDATE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION reject_workspace_append_only_mutation()"
        )
        op.execute(
            f"CREATE TRIGGER trg_{table}_no_delete BEFORE DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION reject_workspace_append_only_mutation()"
        )
    op.execute(
        "CREATE FUNCTION guard_schedule_version_immutable_columns() RETURNS trigger "
        "LANGUAGE plpgsql AS $$ BEGIN IF ROW(NEW.data_plane, "
        "NEW.schedule_version_id, NEW.revision, NEW.environment, NEW.synthetic, "
        "NEW.parent_schedule_version_id, NEW.content_fingerprint, "
        "NEW.immutable_fingerprint, NEW.content_json, NEW.creation_json, "
        "NEW.created_at_utc) IS DISTINCT FROM ROW(OLD.data_plane, "
        "OLD.schedule_version_id, OLD.revision, OLD.environment, OLD.synthetic, "
        "OLD.parent_schedule_version_id, OLD.content_fingerprint, "
        "OLD.immutable_fingerprint, OLD.content_json, OLD.creation_json, "
        "OLD.created_at_utc) THEN RAISE EXCEPTION "
        "'schedule_versions immutable content'; END IF; RETURN NEW; END; $$"
    )
    op.execute(
        "CREATE TRIGGER trg_schedule_versions_immutable_columns BEFORE UPDATE ON "
        "schedule_versions FOR EACH ROW EXECUTE FUNCTION "
        "guard_schedule_version_immutable_columns()"
    )
    op.execute(
        "CREATE TRIGGER trg_schedule_versions_no_delete BEFORE DELETE ON "
        "schedule_versions FOR EACH ROW EXECUTE FUNCTION "
        "reject_workspace_append_only_mutation()"
    )
    op.execute(
        "CREATE FUNCTION guard_export_job_immutable_columns() RETURNS trigger "
        "LANGUAGE plpgsql AS $$ BEGIN IF ROW(NEW.data_plane, NEW.export_job_id, "
        "NEW.environment, NEW.schedule_version_id, "
        "NEW.schedule_content_fingerprint, NEW.target, NEW.package_profile, "
        "NEW.idempotency_scope, NEW.idempotency_key_reference, "
        "NEW.request_fingerprint, NEW.creation_json) IS DISTINCT FROM "
        "ROW(OLD.data_plane, OLD.export_job_id, OLD.environment, "
        "OLD.schedule_version_id, OLD.schedule_content_fingerprint, OLD.target, "
        "OLD.package_profile, OLD.idempotency_scope, "
        "OLD.idempotency_key_reference, OLD.request_fingerprint, "
        "OLD.creation_json) THEN RAISE EXCEPTION 'export_jobs immutable identity'; "
        "END IF; RETURN NEW; END; $$"
    )
    op.execute(
        "CREATE TRIGGER trg_export_jobs_immutable_columns BEFORE UPDATE ON "
        "export_jobs FOR EACH ROW EXECUTE FUNCTION "
        "guard_export_job_immutable_columns()"
    )
    op.execute(
        "CREATE TRIGGER trg_export_jobs_no_delete BEFORE DELETE ON export_jobs "
        "FOR EACH ROW EXECUTE FUNCTION reject_workspace_append_only_mutation()"
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
        for trigger in (
            "trg_export_jobs_no_delete",
            "trg_export_jobs_immutable_columns",
            "trg_publication_results_no_delete",
            "trg_publication_results_no_update",
            "trg_audit_events_no_delete",
            "trg_audit_events_no_update",
            "trg_schedule_versions_no_delete",
            "trg_schedule_versions_immutable_columns",
        ):
            op.execute(f"DROP TRIGGER {trigger}")
    elif dialect == "postgresql":
        op.execute("DROP TRIGGER trg_export_jobs_no_delete ON export_jobs")
        op.execute("DROP TRIGGER trg_export_jobs_immutable_columns ON export_jobs")
        op.execute(
            "DROP TRIGGER trg_publication_results_no_delete ON publication_results"
        )
        op.execute(
            "DROP TRIGGER trg_publication_results_no_update ON publication_results"
        )
        op.execute("DROP TRIGGER trg_audit_events_no_delete ON audit_events")
        op.execute("DROP TRIGGER trg_audit_events_no_update ON audit_events")
        op.execute("DROP TRIGGER trg_schedule_versions_no_delete ON schedule_versions")
        op.execute(
            "DROP TRIGGER trg_schedule_versions_immutable_columns ON schedule_versions"
        )
        op.execute("DROP FUNCTION guard_export_job_immutable_columns()")
        op.execute("DROP FUNCTION guard_schedule_version_immutable_columns()")
        op.execute("DROP FUNCTION reject_workspace_append_only_mutation()")

    op.drop_index("ix_export_jobs_plane_lease", table_name="export_jobs")
    op.drop_index("ix_export_jobs_plane_state_updated", table_name="export_jobs")
    op.drop_table("export_jobs")
    op.drop_table("publication_current_references")
    op.drop_index(
        "ix_publication_results_plane_published", table_name="publication_results"
    )
    op.drop_table("publication_results")
    op.drop_index("ix_audit_events_plane_correlation", table_name="audit_events")
    op.drop_index("ix_audit_events_plane_aggregate_time", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index(
        "ix_schedule_versions_plane_parent_revision", table_name="schedule_versions"
    )
    op.drop_index(
        "ix_schedule_versions_plane_state_created", table_name="schedule_versions"
    )
    op.drop_table("schedule_versions")
