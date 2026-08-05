FROM python:3.13-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN apt-get update && apt-get install -y --no-install-recommends build-essential curl libxml2 libxslt1.1 libpq5 ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /app
RUN python -m pip install --no-cache-dir --upgrade pip setuptools wheel
COPY apps/api/pyproject.toml /tmp/pyproject.toml
RUN python - <<'PY2'
import tomllib, subprocess
with open('/tmp/pyproject.toml','rb') as f: data=tomllib.load(f)
deps=data['project']['dependencies']+data['project']['optional-dependencies']['dev']
subprocess.check_call(['pip','install','--no-cache-dir',*deps])
PY2
RUN useradd --create-home --uid 10001 hubfiscal && chown -R hubfiscal:hubfiscal /app
USER 10001
