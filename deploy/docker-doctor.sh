#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE="${1:-compose.production.yaml}"
ENV_FILE="${2:-.env}"
PULL_IMAGES="${HUBFISCAL_DOCTOR_PULL:-false}"

failures=0

ok() {
  printf '[OK] %s\n' "$1"
}

warn() {
  printf '[AVISO] %s\n' "$1" >&2
}

fail() {
  printf '[ERRO] %s\n' "$1" >&2
  failures=$((failures + 1))
}

if command -v docker >/dev/null 2>&1; then
  ok "Docker encontrado: $(docker --version)"
else
  fail "Docker não está instalado ou não está no PATH."
fi

if docker compose version >/dev/null 2>&1; then
  ok "Docker Compose v2 encontrado: $(docker compose version --short)"
else
  fail "Docker Compose v2 não está disponível."
fi

if [[ -f "$COMPOSE_FILE" ]]; then
  ok "Compose encontrado: $COMPOSE_FILE"
else
  fail "Compose não encontrado: $COMPOSE_FILE"
fi

if [[ -f "$ENV_FILE" ]]; then
  ok "Ambiente encontrado: $ENV_FILE"
else
  fail "Ambiente não encontrado: $ENV_FILE"
fi

if (( failures > 0 )); then
  exit 1
fi

read_env() {
  python3 - "$ENV_FILE" "$1" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

expected = sys.argv[2]
for raw in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
    line = raw.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, value = line.split("=", 1)
    if key.strip() != expected:
        continue
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        print(json.loads(value))
    elif len(value) >= 2 and value[0] == value[-1] == "'":
        print(value[1:-1])
    else:
        print(value)
    raise SystemExit(0)
raise SystemExit(1)
PY
}

required=(
  COMPOSE_PROJECT_NAME INSTANCE_NAME RESOURCE_PREFIX
  IMAGE_REGISTRY IMAGE_NAMESPACE APP_IMAGE_TAG
  HUBFISCAL_SECRET_KEY HUBFISCAL_ENCRYPTION_KEY HUBFISCAL_BOOTSTRAP_TOKEN
  HUBFISCAL_CORS_ORIGINS HUBFISCAL_DATA_ROOT
  WEB_BIND_HOST WEB_PUBLISHED_PORT
  POSTGRES_PASSWORD RABBITMQ_PASSWORD MINIO_PASSWORD
)

for name in "${required[@]}"; do
  value="$(read_env "$name" 2>/dev/null || true)"
  if [[ -z "$value" ]]; then
    fail "$name está ausente ou vazia."
  elif [[ "$value" == *change-me* || "$value" == *SEU_SERVIDOR* || "$value" == *seudominio* ]]; then
    fail "$name ainda contém valor de exemplo: $value"
  else
    ok "$name configurada."
  fi
done

for legacy in HUBFISCAL_IMAGE_TAG GHCR_REGISTRY GHCR_NAMESPACE HUBFISCAL_BIND_HOST HUBFISCAL_HTTP_PORT; do
  value="$(read_env "$legacy" 2>/dev/null || true)"
  if [[ -n "$value" ]]; then
    fail "Variável legada $legacy encontrada; use o novo contrato do .env.example."
  fi
done

image_tag="$(read_env APP_IMAGE_TAG 2>/dev/null || true)"
if [[ "$image_tag" == "latest" ]]; then
  ok "APP_IMAGE_TAG usa latest e acompanhará a release estável mais recente."
else
  warn "APP_IMAGE_TAG está fixada em $image_tag; isso é adequado somente para rollback ou homologação."
fi

secret="$(read_env HUBFISCAL_SECRET_KEY 2>/dev/null || true)"
if [[ -n "$secret" && "${#secret}" -lt 32 ]]; then
  fail "HUBFISCAL_SECRET_KEY possui menos de 32 caracteres."
fi

data_root="$(read_env HUBFISCAL_DATA_ROOT 2>/dev/null || true)"
if [[ -n "$data_root" ]]; then
  if [[ "$data_root" =~ [[:space:]] ]]; then
    fail "HUBFISCAL_DATA_ROOT contém espaço ou comentário no valor: $data_root"
  elif [[ "$data_root" != /* && "$data_root" != ./* && "$data_root" != ../* ]]; then
    fail "HUBFISCAL_DATA_ROOT relativo deve começar com ./ ou ../: $data_root"
  elif mkdir -p "$data_root" 2>/dev/null && [[ -w "$data_root" ]]; then
    ok "Diretório persistente gravável: $data_root"
  else
    fail "Diretório persistente sem permissão de escrita: $data_root"
  fi
fi

http_port="$(read_env WEB_PUBLISHED_PORT 2>/dev/null || echo 58088)"
if [[ ! "$http_port" =~ ^[0-9]+$ ]] || (( http_port < 1 || http_port > 65535 )); then
  fail "WEB_PUBLISHED_PORT inválida: $http_port"
elif command -v ss >/dev/null 2>&1 && ss -ltn "sport = :$http_port" | grep -q LISTEN; then
  fail "A porta $http_port já está em uso."
else
  ok "Porta web $http_port aparentemente disponível."
fi

if docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" config --quiet; then
  ok "Interpolação e sintaxe do Docker Compose aprovadas."
else
  fail "Docker Compose inválido para o ambiente informado."
fi

if [[ "$PULL_IMAGES" == "true" ]]; then
  if docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" pull; then
    ok "Imagens acessíveis no registry."
  else
    fail "Falha ao baixar imagens. Verifique APP_IMAGE_TAG e autenticação no registry."
  fi
fi

if (( failures > 0 )); then
  echo "Diagnóstico concluído com $failures erro(s)." >&2
  exit 1
fi

echo "Diagnóstico Docker aprovado."
