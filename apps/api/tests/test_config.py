from hubfiscal.core.config import Settings


def build_settings(**overrides):
    values = {
        "HUBFISCAL_SECRET_KEY": "s" * 64,
        "HUBFISCAL_ENCRYPTION_KEY": "test-encryption-key",
        "HUBFISCAL_BOOTSTRAP_TOKEN": "test-bootstrap-token",
        "DATABASE_URL": "",
        "DATABASE_URL_SYNC": "",
        "REDIS_URL": "",
        "CELERY_BROKER_URL": "",
        "CELERY_RESULT_BACKEND": "",
        "POSTGRES_PASSWORD": "p@ss:/# word",
        "RABBITMQ_PASSWORD": "rabbit@:/# word",
        "MINIO_ENDPOINT": "http://hubfiscal-minio:9000",
        "MINIO_BUCKET": "hubfiscal-documents",
        "MINIO_ROOT_USER": "hubfiscal",
        "MINIO_ROOT_PASSWORD": "minio-password",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_builds_internal_urls_with_escaped_credentials():
    settings = build_settings()

    assert "p%40ss%3A%2F%23%20word" in settings.database_url
    assert settings.database_url.startswith("postgresql+asyncpg://")
    assert settings.database_url_sync.startswith("postgresql+psycopg://")
    assert "rabbit%40%3A%2F%23%20word" in settings.celery_broker_url
    assert settings.celery_broker_url.endswith("//")
    assert settings.redis_url == "redis://hubfiscal-redis:6379/0"
    assert settings.celery_result_backend == "redis://hubfiscal-redis:6379/1"


def test_explicit_service_urls_have_precedence():
    settings = build_settings(
        DATABASE_URL="postgresql+asyncpg://custom/database",
        DATABASE_URL_SYNC="postgresql+psycopg://custom/database",
        REDIS_URL="redis://custom:6379/4",
        CELERY_BROKER_URL="amqp://custom",
        CELERY_RESULT_BACKEND="redis://custom:6379/5",
    )

    assert settings.database_url == "postgresql+asyncpg://custom/database"
    assert settings.database_url_sync == "postgresql+psycopg://custom/database"
    assert settings.redis_url == "redis://custom:6379/4"
    assert settings.celery_broker_url == "amqp://custom"
    assert settings.celery_result_backend == "redis://custom:6379/5"
