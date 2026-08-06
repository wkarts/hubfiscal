from functools import lru_cache
from typing import Literal
from urllib.parse import quote

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = "Hub Fiscal"
    environment: Literal["development", "test", "production"] = Field(
        default="development",
        alias="HUBFISCAL_ENV",
    )
    debug: bool = Field(default=False, alias="HUBFISCAL_DEBUG")
    secret_key: str = Field(alias="HUBFISCAL_SECRET_KEY")
    encryption_key: str = Field(alias="HUBFISCAL_ENCRYPTION_KEY")
    bootstrap_token: str = Field(alias="HUBFISCAL_BOOTSTRAP_TOKEN")
    access_token_minutes: int = Field(
        default=60,
        alias="HUBFISCAL_ACCESS_TOKEN_MINUTES",
    )
    refresh_token_days: int = Field(
        default=30,
        alias="HUBFISCAL_REFRESH_TOKEN_DAYS",
    )
    cors_origins_raw: str = Field(default="", alias="HUBFISCAL_CORS_ORIGINS")
    log_level: str = Field(default="INFO", alias="HUBFISCAL_LOG_LEVEL")

    # URLs completas continuam aceitas para compatibilidade. Quando ausentes,
    # são construídas com segurança a partir das variáveis separadas.
    database_url: str = Field(default="", alias="DATABASE_URL")
    database_url_sync: str = Field(default="", alias="DATABASE_URL_SYNC")
    redis_url: str = Field(default="", alias="REDIS_URL")
    celery_broker_url: str = Field(default="", alias="CELERY_BROKER_URL")
    celery_result_backend: str = Field(default="", alias="CELERY_RESULT_BACKEND")

    postgres_host: str = Field(default="hubfiscal-postgres", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    postgres_db: str = Field(default="hubfiscal", alias="POSTGRES_DB")
    postgres_user: str = Field(default="hubfiscal", alias="POSTGRES_USER")
    postgres_password: str = Field(default="", alias="POSTGRES_PASSWORD")

    redis_host: str = Field(default="hubfiscal-redis", alias="REDIS_HOST")
    redis_port: int = Field(default=6379, alias="REDIS_PORT")
    redis_db: int = Field(default=0, alias="REDIS_DB")
    celery_result_redis_db: int = Field(
        default=1,
        alias="CELERY_RESULT_REDIS_DB",
    )

    rabbitmq_host: str = Field(default="hubfiscal-rabbitmq", alias="RABBITMQ_HOST")
    rabbitmq_port: int = Field(default=5672, alias="RABBITMQ_PORT")
    rabbitmq_user: str = Field(default="hubfiscal", alias="RABBITMQ_USER")
    rabbitmq_password: str = Field(default="", alias="RABBITMQ_PASSWORD")
    rabbitmq_vhost: str = Field(default="/", alias="RABBITMQ_VHOST")

    minio_endpoint: str = Field(alias="MINIO_ENDPOINT")
    minio_public_endpoint: str = Field(default="", alias="MINIO_PUBLIC_ENDPOINT")
    minio_bucket: str = Field(alias="MINIO_BUCKET")
    minio_region: str = Field(default="us-east-1", alias="MINIO_REGION")
    minio_access_key: str = Field(alias="MINIO_ROOT_USER")
    minio_secret_key: str = Field(alias="MINIO_ROOT_PASSWORD")
    minio_secure: bool = Field(default=False, alias="MINIO_SECURE")

    @property
    def cors_origins(self) -> list[str]:
        return [
            item.strip()
            for item in self.cors_origins_raw.split(",")
            if item.strip()
        ]

    @field_validator("secret_key")
    @classmethod
    def validate_secret(cls, value: str) -> str:
        if len(value) < 32:
            raise ValueError(
                "HUBFISCAL_SECRET_KEY deve ter ao menos 32 caracteres"
            )
        return value

    @model_validator(mode="after")
    def build_internal_urls(self) -> "Settings":
        if not self.database_url or not self.database_url_sync:
            if not self.postgres_password:
                raise ValueError(
                    "POSTGRES_PASSWORD é obrigatória quando DATABASE_URL e "
                    "DATABASE_URL_SYNC não são informadas"
                )
            postgres_user = quote(self.postgres_user, safe="")
            postgres_password = quote(self.postgres_password, safe="")
            postgres_db = quote(self.postgres_db, safe="")

            if not self.database_url:
                self.database_url = (
                    f"postgresql+asyncpg://{postgres_user}:{postgres_password}"
                    f"@{self.postgres_host}:{self.postgres_port}/{postgres_db}"
                )

            if not self.database_url_sync:
                self.database_url_sync = (
                    f"postgresql+psycopg://{postgres_user}:{postgres_password}"
                    f"@{self.postgres_host}:{self.postgres_port}/{postgres_db}"
                )

        if not self.redis_url:
            self.redis_url = (
                f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"
            )

        if not self.celery_result_backend:
            self.celery_result_backend = (
                f"redis://{self.redis_host}:{self.redis_port}/"
                f"{self.celery_result_redis_db}"
            )

        if not self.celery_broker_url:
            if not self.rabbitmq_password:
                raise ValueError(
                    "RABBITMQ_PASSWORD é obrigatória quando "
                    "CELERY_BROKER_URL não é informada"
                )
            rabbitmq_user = quote(self.rabbitmq_user, safe="")
            rabbitmq_password = quote(self.rabbitmq_password, safe="")
            if self.rabbitmq_vhost == "/":
                vhost_path = "/"
            else:
                vhost_path = quote(
                    self.rabbitmq_vhost.lstrip("/"),
                    safe="",
                )
            self.celery_broker_url = (
                f"amqp://{rabbitmq_user}:{rabbitmq_password}"
                f"@{self.rabbitmq_host}:{self.rabbitmq_port}/{vhost_path}"
            )

        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
