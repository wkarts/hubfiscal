"""operational console, DFe cursor, batches and user profile

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("avatar_storage_key", sa.String(length=500), nullable=True))
    op.add_column("users", sa.Column("avatar_content_type", sa.String(length=80), nullable=True))
    op.add_column("users", sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "retrieval_batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("legal_entity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("legal_entities.id", ondelete="SET NULL"), nullable=True),
        sa.Column("requested_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("plugin_installation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("plugin_installations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("document_type", sa.String(length=30), nullable=False, server_default="nfe"),
        sa.Column("environment", sa.String(length=20), nullable=False, server_default="production"),
        sa.Column("mode", sa.String(length=40), nullable=False, server_default="automatic_with_assisted_fallback"),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="queued"),
        sa.Column("total_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("found_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("not_found_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_retrieval_batches_tenant_id", "retrieval_batches", ["tenant_id"])
    op.create_index("ix_retrieval_batches_created_at", "retrieval_batches", ["created_at"])

    op.add_column("retrieval_jobs", sa.Column("environment", sa.String(length=20), nullable=False, server_default="production"))
    op.add_column("retrieval_jobs", sa.Column("operation", sa.String(length=60), nullable=False, server_default="retrieve_by_key"))
    op.add_column("retrieval_jobs", sa.Column("plugin_installation_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("retrieval_jobs", sa.Column("batch_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("retrieval_jobs", sa.Column("parameters", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")))
    op.add_column("retrieval_jobs", sa.Column("result_document_ids", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")))
    op.create_foreign_key(
        "fk_retrieval_jobs_plugin_installation",
        "retrieval_jobs",
        "plugin_installations",
        ["plugin_installation_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_retrieval_jobs_batch",
        "retrieval_jobs",
        "retrieval_batches",
        ["batch_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_retrieval_jobs_batch_id", "retrieval_jobs", ["batch_id"])

    op.create_table(
        "dfe_cursors",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("legal_entity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("legal_entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plugin_installation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("plugin_installations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("environment", sa.String(length=20), nullable=False, server_default="production"),
        sa.Column("last_nsu", sa.String(length=15), nullable=False, server_default="000000000000000"),
        sa.Column("max_nsu", sa.String(length=15), nullable=True),
        sa.Column("last_cstat", sa.String(length=10), nullable=True),
        sa.Column("last_message", sa.Text(), nullable=True),
        sa.Column("blocked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint(
            "tenant_id",
            "legal_entity_id",
            "plugin_installation_id",
            "environment",
            name="uq_dfe_cursor_scope",
        ),
    )
    op.create_index("ix_dfe_cursors_tenant_id", "dfe_cursors", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_dfe_cursors_tenant_id", table_name="dfe_cursors")
    op.drop_table("dfe_cursors")
    op.drop_index("ix_retrieval_jobs_batch_id", table_name="retrieval_jobs")
    op.drop_constraint("fk_retrieval_jobs_batch", "retrieval_jobs", type_="foreignkey")
    op.drop_constraint("fk_retrieval_jobs_plugin_installation", "retrieval_jobs", type_="foreignkey")
    op.drop_column("retrieval_jobs", "result_document_ids")
    op.drop_column("retrieval_jobs", "parameters")
    op.drop_column("retrieval_jobs", "batch_id")
    op.drop_column("retrieval_jobs", "plugin_installation_id")
    op.drop_column("retrieval_jobs", "operation")
    op.drop_column("retrieval_jobs", "environment")
    op.drop_index("ix_retrieval_batches_created_at", table_name="retrieval_batches")
    op.drop_index("ix_retrieval_batches_tenant_id", table_name="retrieval_batches")
    op.drop_table("retrieval_batches")
    op.drop_column("users", "password_changed_at")
    op.drop_column("users", "avatar_content_type")
    op.drop_column("users", "avatar_storage_key")
