"""tenant profiles, resource scopes and alphanumeric CNPJ support

Revision ID: 0002
Revises: 0001
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

ALL_RESOURCES = [
    "dashboard", "companies", "users", "profiles", "certificates", "documents", "query",
    "nfe", "nfce", "cte", "mdfe", "nfse", "dfe", "plugins", "policies", "jobs",
    "integrations", "api_clients", "webhooks", "reports", "audit",
]


def upgrade() -> None:
    op.create_table(
        "access_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("permissions", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("enabled_resources", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("entity_scope_mode", sa.String(length=30), nullable=False, server_default="all"),
        sa.Column("system", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("tenant_id", "key", name="uq_access_profile_tenant_key"),
    )
    op.create_index("ix_access_profiles_tenant_id", "access_profiles", ["tenant_id"])

    op.add_column("memberships", sa.Column("profile_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_memberships_profile_id_access_profiles",
        "memberships",
        "access_profiles",
        ["profile_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_memberships_profile_id", "memberships", ["profile_id"])

    op.add_column("legal_entities", sa.Column("relationship_type", sa.String(length=30), nullable=False, server_default="client"))
    op.add_column("legal_entities", sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column(
        "legal_entities",
        sa.Column(
            "enabled_resources",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'" + __import__("json").dumps(ALL_RESOURCES) + "'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("legal_entities", "enabled_resources")
    op.drop_column("legal_entities", "is_primary")
    op.drop_column("legal_entities", "relationship_type")
    op.drop_index("ix_memberships_profile_id", table_name="memberships")
    op.drop_constraint("fk_memberships_profile_id_access_profiles", "memberships", type_="foreignkey")
    op.drop_column("memberships", "profile_id")
    op.drop_index("ix_access_profiles_tenant_id", table_name="access_profiles")
    op.drop_table("access_profiles")
