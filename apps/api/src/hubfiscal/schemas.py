from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class BootstrapStatus(BaseModel):
    required: bool


class BootstrapAdminRequest(BaseModel):
    token: str
    name: str = Field(min_length=3, max_length=160)
    email: EmailStr
    password: str = Field(min_length=10, max_length=200)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ClientCredentialsRequest(BaseModel):
    client_id: str
    client_secret: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str = Field(min_length=10)
    role: str = "tenant_admin"


class UserOut(ORMModel):
    id: UUID
    name: str
    email: EmailStr
    status: str
    is_platform_admin: bool


class TenantCreate(BaseModel):
    name: str
    slug: str
    type: str = "customer"
    owner_name: str | None = None
    owner_email: EmailStr | None = None
    owner_password: str | None = None


class TenantOut(ORMModel):
    id: UUID
    name: str
    slug: str
    type: str
    status: str
    settings: dict
    created_at: datetime


class LegalEntityCreate(BaseModel):
    document: str
    legal_name: str
    trade_name: str | None = None
    state_registration: str | None = None
    municipal_registrations: list[dict] = []
    city_ibge_code: str | None = None


class LegalEntityOut(ORMModel):
    id: UUID
    tenant_id: UUID
    document: str
    legal_name: str
    trade_name: str | None
    state_registration: str | None
    municipal_registrations: list
    city_ibge_code: str | None
    status: str


class PluginInstallCreate(BaseModel):
    plugin_key: str
    name: str
    legal_entity_id: UUID | None = None
    priority: int = 100
    config: dict = {}
    secrets: dict = {}


class PluginInstallationOut(ORMModel):
    id: UUID
    plugin_key: str
    name: str
    enabled: bool
    priority: int
    config: dict
    health_status: str


class RoutingPolicyCreate(BaseModel):
    name: str
    legal_entity_id: UUID | None = None
    document_type: str = "nfe"
    operation: str = "retrieve_by_key"
    steps: list[dict]
    settings: dict = {}


class RoutingPolicyOut(ORMModel):
    id: UUID
    name: str
    document_type: str
    operation: str
    enabled: bool
    steps: list
    settings: dict


class RetrievalJobCreate(BaseModel):
    legal_entity_id: UUID | None = None
    document_type: str = "nfe"
    access_key: str = Field(min_length=1, max_length=60)
    mode: str = "automatic_with_assisted_fallback"


class RetrievalJobOut(ORMModel):
    id: UUID
    tenant_id: UUID
    document_type: str
    access_key: str | None
    mode: str
    status: str
    progress: int
    result_document_id: UUID | None
    attempts: list
    error_message: str | None
    human_action: dict | None
    created_at: datetime
    updated_at: datetime


class DocumentOut(ORMModel):
    id: UUID
    tenant_id: UUID
    legal_entity_id: UUID | None
    document_type: str
    access_key: str
    schema_name: str | None
    document_level: str
    issuer_document: str | None
    recipient_document: str | None
    issued_at: datetime | None
    total_amount: float | None
    status: str
    sha256: str | None
    signature_valid: bool | None
    protocol_valid: bool | None
    metadata_json: dict
    created_at: datetime


class ApiClientCreate(BaseModel):
    name: str
    scopes: list[str] = ["documents:read", "documents:retrieve"]
    entity_scope: list[str] = []


class ApiClientCreated(BaseModel):
    id: UUID
    name: str
    client_id: str
    client_secret: str
    scopes: list[str]


class DashboardResponse(BaseModel):
    totals: dict[str, int | float]
    documents_by_type: list[dict[str, Any]]
    jobs_by_status: list[dict[str, Any]]
    recent_jobs: list[dict[str, Any]]
    service_health: list[dict[str, Any]]
