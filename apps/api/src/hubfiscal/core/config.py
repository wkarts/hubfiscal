from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Hub Fiscal"
    environment: Literal["development", "test", "production"] = Field(
        default="development", alias="HUBFISCAL_ENV"
    )
    debug: bool = Field(default=False, alias="HUBFISCAL_DEBUG")
    secret_key: str = Field(alias="HUBFISCAL_SECRET_KEY")
    encryption_key: str = Field(alias="HUBFISCAL_ENCRYPTION_KEY")
    bootstrap_token: str = Field(alias="HUBFISCAL_BOOTSTRAP_TOKEN")
    access_token_minutes: int = Field(default=60, alias="HUBFISCAL_ACCESS_TOKEN_MINUTES")
    refresh_token_days: int = Field(default=30, alias="HUBFISCAL_REFRESH_TOKEN_DAYS")
    cors_origins_raw: str = Field(default="", alias="HUBFISCAL_CORS_ORIGINS")
    log_level: str = Field(default="INFO", alias="HUBFISCAL_LOG_LEVEL")

    database_url: str = Field(alias="DATABASE_URL")
    database_url_sync: str = Field(alias="DATABASE_URL_SYNC")
    redis_url: str = Field(alias="REDIS_URL")
    celery_broker_url: str = Field(alias="CELERY_BROKER_URL")
    celery_result_backend: str = Field(alias="CELERY_RESULT_BACKEND")

    minio_endpoint: str = Field(alias="MINIO_ENDPOINT")
    minio_public_endpoint: str = Field(default="", alias="MINIO_PUBLIC_ENDPOINT")
    minio_bucket: str = Field(alias="MINIO_BUCKET")
    minio_region: str = Field(default="us-east-1", alias="MINIO_REGION")
    minio_access_key: str = Field(alias="MINIO_ROOT_USER")
    minio_secret_key: str = Field(alias="MINIO_ROOT_PASSWORD")
    minio_secure: bool = Field(default=False, alias="MINIO_SECURE")

    @property
    def cors_origins(self) -> list[str]:
        return [item.strip() for item in self.cors_origins_raw.split(",") if item.strip()]

    @field_validator("secret_key")
    @classmethod
    def validate_secret(cls, value: str) -> str:
        if len(value) < 32:
            raise ValueError("HUBFISCAL_SECRET_KEY deve ter ao menos 32 caracteres")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
