"""initial schema

Revision ID: 0001
Revises:

A revisão inicial precisa permanecer congelada no schema que existia quando ela
foi publicada. Não importe Base.metadata aqui: modelos futuros fariam uma
instalação nova criar colunas/tabelas antes das migrations que as introduzem.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB()


def timestamps() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("is_platform_admin", sa.Boolean(), nullable=False),
        *timestamps(),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "tenants",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("type", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("settings", JSONB, nullable=False),
        *timestamps(),
        sa.UniqueConstraint("slug", name="uq_tenants_slug"),
    )
    op.create_index("ix_tenants_slug", "tenants", ["slug"])

    op.create_table(
        "memberships",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(length=60), nullable=False),
        sa.Column("permissions", JSONB, nullable=False),
        sa.Column("entity_scope", JSONB, nullable=False),
        *timestamps(),
        sa.UniqueConstraint("tenant_id", "user_id", name="uq_membership_tenant_user"),
    )
    op.create_index("ix_memberships_tenant_id", "memberships", ["tenant_id"])
    op.create_index("ix_memberships_user_id", "memberships", ["user_id"])

    op.create_table(
        "legal_entities",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document", sa.String(length=20), nullable=False),
        sa.Column("legal_name", sa.String(length=200), nullable=False),
        sa.Column("trade_name", sa.String(length=200), nullable=True),
        sa.Column("state_registration", sa.String(length=40), nullable=True),
        sa.Column("municipal_registrations", JSONB, nullable=False),
        sa.Column("city_ibge_code", sa.String(length=10), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("metadata", JSONB, nullable=False),
        *timestamps(),
        sa.UniqueConstraint("tenant_id", "document", name="uq_legal_entity_document"),
    )
    op.create_index("ix_legal_entities_tenant_id", "legal_entities", ["tenant_id"])
    op.create_index("ix_legal_entities_document", "legal_entities", ["document"])

    op.create_table(
        "digital_certificates",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("legal_entity_id", UUID, sa.ForeignKey("legal_entities.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("certificate_type", sa.String(length=10), nullable=False),
        sa.Column("subject_document", sa.String(length=20), nullable=True),
        sa.Column("serial_number", sa.String(length=180), nullable=True),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fingerprint_sha256", sa.String(length=64), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("encrypted_password", sa.LargeBinary(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        *timestamps(),
        sa.UniqueConstraint("fingerprint_sha256", name="uq_digital_certificates_fingerprint_sha256"),
    )
    op.create_index("ix_digital_certificates_tenant_id", "digital_certificates", ["tenant_id"])

    op.create_table(
        "plugin_definitions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("version", sa.String(length=40), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("capabilities", JSONB, nullable=False),
        sa.Column("config_schema", JSONB, nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        *timestamps(),
        sa.UniqueConstraint("key", name="uq_plugin_definitions_key"),
    )
    op.create_index("ix_plugin_definitions_key", "plugin_definitions", ["key"])

    op.create_table(
        "plugin_installations",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("legal_entity_id", UUID, sa.ForeignKey("legal_entities.id", ondelete="CASCADE"), nullable=True),
        sa.Column("plugin_key", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("config", JSONB, nullable=False),
        sa.Column("encrypted_secrets", sa.LargeBinary(), nullable=True),
        sa.Column("health_status", sa.String(length=30), nullable=False),
        sa.Column("last_healthcheck_at", sa.DateTime(timezone=True), nullable=True),
        *timestamps(),
        sa.UniqueConstraint("tenant_id", "plugin_key", "name", name="uq_plugin_installation"),
    )
    op.create_index("ix_plugin_installations_tenant_id", "plugin_installations", ["tenant_id"])
    op.create_index("ix_plugin_installations_plugin_key", "plugin_installations", ["plugin_key"])

    op.create_table(
        "routing_policies",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("legal_entity_id", UUID, sa.ForeignKey("legal_entities.id", ondelete="CASCADE"), nullable=True),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("document_type", sa.String(length=30), nullable=False),
        sa.Column("operation", sa.String(length=60), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("steps", JSONB, nullable=False),
        sa.Column("settings", JSONB, nullable=False),
        *timestamps(),
    )
    op.create_index("ix_routing_policies_tenant_id", "routing_policies", ["tenant_id"])

    op.create_table(
        "fiscal_documents",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("legal_entity_id", UUID, sa.ForeignKey("legal_entities.id", ondelete="SET NULL"), nullable=True),
        sa.Column("document_type", sa.String(length=30), nullable=False),
        sa.Column("access_key", sa.String(length=60), nullable=False),
        sa.Column("schema_name", sa.String(length=80), nullable=True),
        sa.Column("document_level", sa.String(length=30), nullable=False),
        sa.Column("issuer_document", sa.String(length=20), nullable=True),
        sa.Column("recipient_document", sa.String(length=20), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("signature_valid", sa.Boolean(), nullable=True),
        sa.Column("protocol_valid", sa.Boolean(), nullable=True),
        sa.Column("metadata", JSONB, nullable=False),
        *timestamps(),
        sa.UniqueConstraint("tenant_id", "document_type", "access_key", name="uq_document_access_key"),
    )
    op.create_index("ix_fiscal_documents_tenant_id", "fiscal_documents", ["tenant_id"])
    op.create_index("ix_fiscal_documents_document_type", "fiscal_documents", ["document_type"])
    op.create_index("ix_fiscal_documents_access_key", "fiscal_documents", ["access_key"])
    op.create_index("ix_fiscal_documents_issuer_document", "fiscal_documents", ["issuer_document"])
    op.create_index("ix_fiscal_documents_recipient_document", "fiscal_documents", ["recipient_document"])
    op.create_index("ix_fiscal_documents_sha256", "fiscal_documents", ["sha256"])
    op.create_index("ix_documents_tenant_issued", "fiscal_documents", ["tenant_id", "issued_at"])

    op.create_table(
        "document_sources",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_id", UUID, sa.ForeignKey("fiscal_documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_key", sa.String(length=100), nullable=False),
        sa.Column("external_id", sa.String(length=180), nullable=True),
        sa.Column("authenticity", sa.String(length=30), nullable=False),
        sa.Column("metadata", JSONB, nullable=False),
        *timestamps(),
    )
    op.create_index("ix_document_sources_tenant_id", "document_sources", ["tenant_id"])
    op.create_index("ix_document_sources_document_id", "document_sources", ["document_id"])

    op.create_table(
        "retrieval_jobs",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("legal_entity_id", UUID, sa.ForeignKey("legal_entities.id", ondelete="SET NULL"), nullable=True),
        sa.Column("requested_by", UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("document_type", sa.String(length=30), nullable=False),
        sa.Column("access_key", sa.String(length=60), nullable=True),
        sa.Column("mode", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("result_document_id", UUID, sa.ForeignKey("fiscal_documents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("attempts", JSONB, nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("human_action", JSONB, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        *timestamps(),
    )
    op.create_index("ix_retrieval_jobs_tenant_id", "retrieval_jobs", ["tenant_id"])
    op.create_index("ix_retrieval_jobs_access_key", "retrieval_jobs", ["access_key"])

    op.create_table(
        "api_clients",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("client_id", sa.String(length=100), nullable=False),
        sa.Column("secret_hash", sa.Text(), nullable=False),
        sa.Column("scopes", JSONB, nullable=False),
        sa.Column("entity_scope", JSONB, nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        *timestamps(),
        sa.UniqueConstraint("client_id", name="uq_api_clients_client_id"),
    )
    op.create_index("ix_api_clients_tenant_id", "api_clients", ["tenant_id"])
    op.create_index("ix_api_clients_client_id", "api_clients", ["client_id"])

    op.create_table(
        "webhooks",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("url", sa.String(length=500), nullable=False),
        sa.Column("events", JSONB, nullable=False),
        sa.Column("secret_encrypted", sa.LargeBinary(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        *timestamps(),
    )
    op.create_index("ix_webhooks_tenant_id", "webhooks", ["tenant_id"])

    op.create_table(
        "audit_events",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, sa.ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("resource_type", sa.String(length=100), nullable=False),
        sa.Column("resource_id", sa.String(length=100), nullable=True),
        sa.Column("ip_address", sa.String(length=80), nullable=True),
        sa.Column("details", JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_events_tenant_id", "audit_events", ["tenant_id"])
    op.create_index("ix_audit_events_action", "audit_events", ["action"])
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"])


def downgrade() -> None:
    for table in (
        "audit_events",
        "webhooks",
        "api_clients",
        "retrieval_jobs",
        "document_sources",
        "fiscal_documents",
        "routing_policies",
        "plugin_installations",
        "plugin_definitions",
        "digital_certificates",
        "legal_entities",
        "memberships",
        "tenants",
        "users",
    ):
        op.drop_table(table)
