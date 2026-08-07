from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, LargeBinary, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .core.database import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class UserStatus(StrEnum):
    ACTIVE = "active"
    INVITED = "invited"
    BLOCKED = "blocked"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    HUMAN_ACTION_REQUIRED = "human_action_required"
    COMPLETED = "completed"
    PARTIAL = "partial"
    NOT_FOUND = "not_found"
    FAILED = "failed"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class User(Base, TimestampMixin):
    __tablename__ = "users"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(160))
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default=UserStatus.ACTIVE)
    is_platform_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    memberships: Mapped[list[Membership]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Tenant(Base, TimestampMixin):
    __tablename__ = "tenants"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(180))
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    type: Mapped[str] = mapped_column(String(30), default="customer")
    status: Mapped[str] = mapped_column(String(30), default="active")
    settings: Mapped[dict] = mapped_column(JSONB, default=dict)
    memberships: Mapped[list[Membership]] = relationship(back_populates="tenant", cascade="all, delete-orphan")
    access_profiles: Mapped[list[AccessProfile]] = relationship(back_populates="tenant", cascade="all, delete-orphan")


class AccessProfile(Base, TimestampMixin):
    __tablename__ = "access_profiles"
    __table_args__ = (UniqueConstraint("tenant_id", "key", name="uq_access_profile_tenant_key"),)
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    permissions: Mapped[list] = mapped_column(JSONB, default=list)
    enabled_resources: Mapped[list] = mapped_column(JSONB, default=list)
    entity_scope_mode: Mapped[str] = mapped_column(String(30), default="all")
    system: Mapped[bool] = mapped_column(Boolean, default=False)
    tenant: Mapped[Tenant] = relationship(back_populates="access_profiles")


class Membership(Base, TimestampMixin):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("tenant_id", "user_id", name="uq_membership_tenant_user"),)
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    profile_id: Mapped[UUID | None] = mapped_column(ForeignKey("access_profiles.id", ondelete="SET NULL"), nullable=True, index=True)
    role: Mapped[str] = mapped_column(String(60), default="tenant_admin")
    permissions: Mapped[list] = mapped_column(JSONB, default=list)
    entity_scope: Mapped[list] = mapped_column(JSONB, default=list)
    tenant: Mapped[Tenant] = relationship(back_populates="memberships")
    user: Mapped[User] = relationship(back_populates="memberships")
    profile: Mapped[AccessProfile | None] = relationship()


class LegalEntity(Base, TimestampMixin):
    __tablename__ = "legal_entities"
    __table_args__ = (UniqueConstraint("tenant_id", "document", name="uq_legal_entity_document"),)
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    document: Mapped[str] = mapped_column(String(20), index=True)
    legal_name: Mapped[str] = mapped_column(String(200))
    trade_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    state_registration: Mapped[str | None] = mapped_column(String(40), nullable=True)
    municipal_registrations: Mapped[list] = mapped_column(JSONB, default=list)
    city_ibge_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    relationship_type: Mapped[str] = mapped_column(String(30), default="client")
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled_resources: Mapped[list] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(String(30), default="active")
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)


class DigitalCertificate(Base, TimestampMixin):
    __tablename__ = "digital_certificates"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    legal_entity_id: Mapped[UUID | None] = mapped_column(ForeignKey("legal_entities.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str] = mapped_column(String(180))
    certificate_type: Mapped[str] = mapped_column(String(10), default="A1")
    subject_document: Mapped[str | None] = mapped_column(String(20), nullable=True)
    serial_number: Mapped[str | None] = mapped_column(String(180), nullable=True)
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fingerprint_sha256: Mapped[str] = mapped_column(String(64), unique=True)
    storage_key: Mapped[str] = mapped_column(String(500))
    encrypted_password: Mapped[bytes] = mapped_column(LargeBinary)
    status: Mapped[str] = mapped_column(String(30), default="active")


class PluginDefinition(Base, TimestampMixin):
    __tablename__ = "plugin_definitions"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    key: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(180))
    version: Mapped[str] = mapped_column(String(40))
    description: Mapped[str] = mapped_column(Text, default="")
    capabilities: Mapped[dict] = mapped_column(JSONB, default=dict)
    config_schema: Mapped[dict] = mapped_column(JSONB, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class PluginInstallation(Base, TimestampMixin):
    __tablename__ = "plugin_installations"
    __table_args__ = (UniqueConstraint("tenant_id", "plugin_key", "name", name="uq_plugin_installation"),)
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    legal_entity_id: Mapped[UUID | None] = mapped_column(ForeignKey("legal_entities.id", ondelete="CASCADE"), nullable=True)
    plugin_key: Mapped[str] = mapped_column(String(100), index=True)
    name: Mapped[str] = mapped_column(String(180))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[int] = mapped_column(Integer, default=100)
    config: Mapped[dict] = mapped_column(JSONB, default=dict)
    encrypted_secrets: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    health_status: Mapped[str] = mapped_column(String(30), default="unknown")
    last_healthcheck_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RoutingPolicy(Base, TimestampMixin):
    __tablename__ = "routing_policies"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    legal_entity_id: Mapped[UUID | None] = mapped_column(ForeignKey("legal_entities.id", ondelete="CASCADE"), nullable=True)
    name: Mapped[str] = mapped_column(String(180))
    document_type: Mapped[str] = mapped_column(String(30), default="nfe")
    operation: Mapped[str] = mapped_column(String(60), default="retrieve_by_key")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    steps: Mapped[list] = mapped_column(JSONB, default=list)
    settings: Mapped[dict] = mapped_column(JSONB, default=dict)


class FiscalDocument(Base, TimestampMixin):
    __tablename__ = "fiscal_documents"
    __table_args__ = (
        UniqueConstraint("tenant_id", "document_type", "access_key", name="uq_document_access_key"),
        Index("ix_documents_tenant_issued", "tenant_id", "issued_at"),
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    legal_entity_id: Mapped[UUID | None] = mapped_column(ForeignKey("legal_entities.id", ondelete="SET NULL"), nullable=True)
    document_type: Mapped[str] = mapped_column(String(30), index=True)
    access_key: Mapped[str] = mapped_column(String(60), index=True)
    schema_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    document_level: Mapped[str] = mapped_column(String(30), default="complete")
    issuer_document: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    recipient_document: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_amount: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="authorized")
    storage_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    signature_valid: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    protocol_valid: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)


class DocumentSource(Base, TimestampMixin):
    __tablename__ = "document_sources"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("fiscal_documents.id", ondelete="CASCADE"), index=True)
    source_key: Mapped[str] = mapped_column(String(100))
    external_id: Mapped[str | None] = mapped_column(String(180), nullable=True)
    authenticity: Mapped[str] = mapped_column(String(30), default="original")
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)


class RetrievalJob(Base, TimestampMixin):
    __tablename__ = "retrieval_jobs"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    legal_entity_id: Mapped[UUID | None] = mapped_column(ForeignKey("legal_entities.id", ondelete="SET NULL"), nullable=True)
    requested_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    document_type: Mapped[str] = mapped_column(String(30), default="nfe")
    access_key: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
    mode: Mapped[str] = mapped_column(String(40), default="automatic_with_assisted_fallback")
    status: Mapped[str] = mapped_column(String(40), default=JobStatus.QUEUED)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    result_document_id: Mapped[UUID | None] = mapped_column(ForeignKey("fiscal_documents.id", ondelete="SET NULL"), nullable=True)
    attempts: Mapped[list] = mapped_column(JSONB, default=list)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    human_action: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ApiClient(Base, TimestampMixin):
    __tablename__ = "api_clients"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(180))
    client_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    secret_hash: Mapped[str] = mapped_column(Text)
    scopes: Mapped[list] = mapped_column(JSONB, default=list)
    entity_scope: Mapped[list] = mapped_column(JSONB, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Webhook(Base, TimestampMixin):
    __tablename__ = "webhooks"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(180))
    url: Mapped[str] = mapped_column(String(500))
    events: Mapped[list] = mapped_column(JSONB, default=list)
    secret_encrypted: Mapped[bytes] = mapped_column(LargeBinary)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID | None] = mapped_column(ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(120), index=True)
    resource_type: Mapped[str] = mapped_column(String(100))
    resource_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(80), nullable=True)
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
