#!/usr/bin/env bash
set -euo pipefail

DEPLOY_DIR="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
COMPOSE_FILE="$DEPLOY_DIR/compose.yaml"
ENV_FILE="$DEPLOY_DIR/.env"
PENDING_ENV="$DEPLOY_DIR/.env.new"
ROLLBACK_ENV="$DEPLOY_DIR/.env.rollback"
VERSION_FILE="$DEPLOY_DIR/.deployed-version"

cd "$DEPLOY_DIR"

if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo "Compose não encontrado: $COMPOSE_FILE" >&2
  exit 1
fi
if [[ ! -f "$PENDING_ENV" && ! -f "$ENV_FILE" ]]; then
  echo "Nenhum arquivo de ambiente disponível." >&2
  exit 1
fi

PREVIOUS_VERSION=""
if [[ -f "$VERSION_FILE" ]]; then
  PREVIOUS_VERSION="$(tr -d '[:space:]' < "$VERSION_FILE")"
fi

backup_database() {
  [[ -f "$ENV_FILE" ]] || return 0
  local data_root backup_dir backup_file
  data_root="$(sed -n 's/^HUBFISCAL_DATA_ROOT=//p' "$ENV_FILE" | tail -n1)"
  [[ -n "$data_root" ]] || return 0
  backup_dir="$data_root/backups"
  backup_file="$backup_dir/postgres-before-${PREVIOUS_VERSION:-unknown}-$(date -u +'%Y%m%dT%H%M%SZ').sql.gz"
  mkdir -p "$backup_dir"

  if docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" ps --status running hubfiscal-postgres | grep -q hubfiscal-postgres; then
    echo "Gerando backup preventivo em $backup_file..."
    docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T hubfiscal-postgres \
      sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB"' | gzip -9 > "$backup_file"
    test -s "$backup_file"
  fi
}

if [[ -f "$PENDING_ENV" ]]; then
  if [[ -f "$ENV_FILE" ]]; then
    cp "$ENV_FILE" "$ROLLBACK_ENV"
    chmod 600 "$ROLLBACK_ENV"
    backup_database
  fi
  mv "$PENDING_ENV" "$ENV_FILE"
fi
chmod 600 "$ENV_FILE"

CURRENT_VERSION="$(sed -n 's/^HUBFISCAL_IMAGE_TAG=//p' "$ENV_FILE" | tail -n1)"
if [[ -z "$CURRENT_VERSION" ]]; then
  echo "HUBFISCAL_IMAGE_TAG não definido em $ENV_FILE" >&2
  exit 1
fi

compose() {
  docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" "$@"
}

rollback() {
  if [[ ! -f "$ROLLBACK_ENV" ]]; then
    echo "Rollback indisponível: não existe ambiente anterior." >&2
    return 1
  fi
  echo "Restaurando containers da versão anterior ${PREVIOUS_VERSION:-desconhecida}..."
  cp "$ROLLBACK_ENV" "$ENV_FILE"
  chmod 600 "$ENV_FILE"
  compose pull
  compose up -d --remove-orphans --force-recreate
  "$DEPLOY_DIR/healthcheck.sh" "$DEPLOY_DIR"
}

trap 'echo "Deploy interrompido." >&2' INT TERM

echo "Validando Compose da versão $CURRENT_VERSION..."
compose config --quiet

echo "Baixando imagens da versão $CURRENT_VERSION..."
compose pull

echo "Aplicando stack Hub Fiscal..."
compose up -d --remove-orphans --force-recreate

if ! "$DEPLOY_DIR/healthcheck.sh" "$DEPLOY_DIR"; then
  echo "Health check falhou para $CURRENT_VERSION." >&2
  rollback || true
  exit 1
fi

printf '%s\n' "$CURRENT_VERSION" > "$VERSION_FILE"
rm -f "$ROLLBACK_ENV"
compose ps

echo "Deploy Hub Fiscal $CURRENT_VERSION concluído com sucesso."
