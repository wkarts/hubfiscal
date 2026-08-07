from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


EnvironmentName = Literal["production", "homologation"]
DocumentTypeName = Literal["nfe", "nfce", "cte", "mdfe", "nfse"]


class PluginInstallRequest(BaseModel):
    plugin_key: str
    name: str = Field(min_length=2, max_length=180)
    legal_entity_id: UUID | None = None
    priority: int = Field(default=100, ge=1, le=9999)
    enabled: bool = True
    config: dict[str, Any] = Field(default_factory=dict)
    secrets: dict[str, Any] = Field(default_factory=dict)


class PluginInstallationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=180)
    legal_entity_id: UUID | None = None
    priority: int | None = Field(default=None, ge=1, le=9999)
    enabled: bool | None = None
    config: dict[str, Any] | None = None
    secrets: dict[str, Any] | None = None
    clear_secrets: bool = False


class RetrievalJobRequest(BaseModel):
    legal_entity_id: UUID | None = None
    plugin_installation_id: UUID | None = None
    document_type: DocumentTypeName = "nfe"
    access_key: str = Field(min_length=1, max_length=60)
    environment: EnvironmentName = "production"
    operation: str = "retrieve_by_key"
    mode: str = "automatic_with_assisted_fallback"
    parameters: dict[str, Any] = Field(default_factory=dict)


class RetrievalJobResponse(ORMModel):
    id: UUID
    tenant_id: UUID
    legal_entity_id: UUID | None
    plugin_installation_id: UUID | None
    batch_id: UUID | None
    document_type: str
    access_key: str | None
    environment: str
    operation: str
    parameters: dict
    mode: str
    status: str
    progress: int
    result_document_id: UUID | None
    result_document_ids: list
    attempts: list
    error_message: str | None
    human_action: dict | None
    created_at: datetime
    updated_at: datetime


class RetrievalBatchCreate(BaseModel):
    legal_entity_id: UUID | None = None
    plugin_installation_id: UUID | None = None
    document_type: DocumentTypeName = "nfe"
    environment: EnvironmentName = "production"
    mode: str = "automatic_with_assisted_fallback"
    access_keys: list[str] = Field(min_length=1, max_length=500)

    @field_validator("access_keys")
    @classmethod
    def normalize_keys(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for raw in value:
            key = "".join(str(raw).split()).strip()
            if not key or key in seen:
                continue
            if len(key) > 60:
                raise ValueError(f"Chave/identificador muito longo: {key[:20]}…")
            normalized.append(key)
            seen.add(key)
        if not normalized:
            raise ValueError("Informe ao menos uma chave")
        return normalized


class RetrievalBatchOut(ORMModel):
    id: UUID
    tenant_id: UUID
    legal_entity_id: UUID | None
    plugin_installation_id: UUID | None
    document_type: str
    environment: str
    mode: str
    status: str
    total_count: int
    completed_count: int
    found_count: int
    not_found_count: int
    failed_count: int
    created_at: datetime
    updated_at: datetime


class RetrievalBatchDetail(RetrievalBatchOut):
    jobs: list[RetrievalJobResponse] = Field(default_factory=list)


class DfeDistributionRequest(BaseModel):
    legal_entity_id: UUID
    plugin_installation_id: UUID
    environment: EnvironmentName = "production"
    operation: Literal["distNSU", "consNSU", "consChNFe"] = "distNSU"
    nsu: str | None = None
    access_key: str | None = None

    @field_validator("nsu")
    @classmethod
    def validate_nsu(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        digits = "".join(ch for ch in value if ch.isdigit())
        if len(digits) > 15:
            raise ValueError("NSU deve possuir no máximo 15 dígitos")
        return digits.zfill(15)


class DfeCursorOut(ORMModel):
    id: UUID
    legal_entity_id: UUID
    plugin_installation_id: UUID
    environment: str
    last_nsu: str
    max_nsu: str | None
    last_cstat: str | None
    last_message: str | None
    blocked_until: datetime | None
    last_checked_at: datetime | None


class ProfileUpdate(BaseModel):
    name: str = Field(min_length=3, max_length=160)
    email: EmailStr


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=200)

    @field_validator("new_password")
    @classmethod
    def password_quality(cls, value: str) -> str:
        if value.strip() != value:
            raise ValueError("A senha não pode iniciar ou terminar com espaços")
        return value
