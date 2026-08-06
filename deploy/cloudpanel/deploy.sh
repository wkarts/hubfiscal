#!/usr/bin/env bash
set -euo pipefail

DEPLOY_DIR="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
COMPOSE_FILE="$DEPLOY_DIR/compose.yaml"
ENV_FILE="$DEPLOY_DIR/.env"
PENDING_ENV="$DEPLOY_DIR/.env.new"
PREVIOUS_ENV="$DEPLOY_DIR/.env.previous"
VERSION_FILE="$DEPLOY_DIR/.deployed-version"
LOCK_FILE="$DEPLOY_DIR/.deploy.lock"

mkdir -p "$DEPLOY_DIR"
cd "$DEPLOY_DIR"

if command -v flock >/dev/null 2>&1; then
  exec 9>"$LOCK_FILE"
  if ! flock -n 9; then
    echo "Já existe outro deploy do Hub Fiscal em execução." >&2
    exit 1
  fi
fi

if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo "Compose não encontrado: $COMPOSE_FILE" >&2
  exit 1
fi
if [[ ! -f "$PENDING_ENV" && ! -f "$ENV_FILE" ]]; then
  echo "Nenhum arquivo de ambiente disponível em $DEPLOY_DIR." >&2
  exit 1
fi

read_env() {
  local file="$1"
  local key="$2"
  python3 - "$file" "$key" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
expected = sys.argv[2]
for raw in path.read_text(encoding="utf-8").splitlines():
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

compose_with() {
  local env_file="$1"
  shift
  docker compose --env-file "$env_file" -f "$COMPOSE_FILE" "$@"
}

PREVIOUS_VERSION=""
if [[ -f "$VERSION_FILE" ]]; then
  PREVIOUS_VERSION="$(tr -d '[:space:]' < "$VERSION_FILE")"
fi

backup_database() {
  [[ -f "$ENV_FILE" ]] || return 0

  local data_root backup_dir backup_file
  data_root="$(read_env "$ENV_FILE" HUBFISCAL_DATA_ROOT 2>/dev/null || true)"
  [[ -n "$data_root" ]] || return 0
  backup_dir="$data_root/backups"
  backup_file="$backup_dir/postgres-before-${PREVIOUS_VERSION:-unknown}-$(date -u +'%Y%m%dT%H%M%SZ').sql.gz"
  mkdir -p "$backup_dir"

  if compose_with "$ENV_FILE" ps --status running --services | grep -qx hubfiscal-postgres; then
    echo "Gerando backup preventivo em $backup_file..."
    compose_with "$ENV_FILE" exec -T hubfiscal-postgres \
      sh -ec 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
      | gzip -9 > "$backup_file"
    if [[ ! -s "$backup_file" ]]; then
      echo "O backup preventivo ficou vazio; deploy cancelado." >&2
      rm -f "$backup_file"
      return 1
    fi
  fi
}

rollback() {
  if [[ ! -f "$PREVIOUS_ENV" ]]; then
    echo "Rollback automático indisponível: não existe .env anterior." >&2
    return 1
  fi

  echo "Restaurando versão anterior ${PREVIOUS_VERSION:-desconhecida}..."
  cp "$PREVIOUS_ENV" "$ENV_FILE"
  chmod 600 "$ENV_FILE"

  compose_with "$ENV_FILE" config --quiet
  compose_with "$ENV_FILE" pull
  compose_with "$ENV_FILE" up -d --remove-orphans --force-recreate
  "$DEPLOY_DIR/healthcheck.sh" "$DEPLOY_DIR"
}

if [[ -f "$PENDING_ENV" ]]; then
  chmod 600 "$PENDING_ENV"
  compose_with "$PENDING_ENV" config --quiet

  if [[ -f "$ENV_FILE" ]]; then
    backup_database
    cp "$ENV_FILE" "$PREVIOUS_ENV"
    chmod 600 "$PREVIOUS_ENV"
  fi

  mv "$PENDING_ENV" "$ENV_FILE"
fi
chmod 600 "$ENV_FILE"

CURRENT_VERSION="$(read_env "$ENV_FILE" HUBFISCAL_IMAGE_TAG 2>/dev/null || true)"
if [[ -z "$CURRENT_VERSION" ]]; then
  echo "HUBFISCAL_IMAGE_TAG não definida em $ENV_FILE" >&2
  exit 1
fi

failure() {
  local stage="$1"
  echo "Falha durante: $stage (versão $CURRENT_VERSION)." >&2
  if ! rollback; then
    echo "Rollback automático não pôde ser concluído." >&2
  fi
  exit 1
}

trap 'echo "Deploy interrompido pelo sistema." >&2' INT TERM

echo "Validando Compose da versão $CURRENT_VERSION..."
compose_with "$ENV_FILE" config --quiet || failure "validação do Compose"

echo "Baixando imagens da versão $CURRENT_VERSION..."
compose_with "$ENV_FILE" pull || failure "download das imagens"

echo "Aplicando stack Hub Fiscal $CURRENT_VERSION..."
compose_with "$ENV_FILE" up -d --remove-orphans --force-recreate \
  || failure "inicialização dos containers"

if ! "$DEPLOY_DIR/healthcheck.sh" "$DEPLOY_DIR"; then
  failure "health check"
fi

printf '%s\n' "$CURRENT_VERSION" > "$VERSION_FILE"
compose_with "$ENV_FILE" ps

echo "Deploy Hub Fiscal $CURRENT_VERSION concluído com sucesso."
