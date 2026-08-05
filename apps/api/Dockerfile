FROM python:3.13-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN apt-get update && apt-get install -y --no-install-recommends build-essential curl libxml2 libxslt1.1 libpq5 ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY apps/api/pyproject.toml ./pyproject.toml
COPY apps/api/src ./src
COPY apps/api/alembic ./alembic
COPY apps/api/alembic.ini ./alembic.ini
COPY apps/api/tests ./tests
COPY apps/api/entrypoint.sh ./entrypoint.sh
COPY VERSION /app/VERSION
RUN pip install --no-cache-dir --no-build-isolation '.[dev]' && chmod +x /app/entrypoint.sh && useradd --create-home --uid 10001 hubfiscal && chown -R hubfiscal:hubfiscal /app
USER 10001
ENV PYTHONPATH=/app/src
EXPOSE 8080
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["api"]
