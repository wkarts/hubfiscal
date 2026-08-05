#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Uso: $0 <diretorio-do-backup>" >&2
  exit 1
fi

BACKUP_DIR="$(realpath "$1")"
[[ -f "$BACKUP_DIR/database.dump" ]] || { echo "database.dump não encontrado" >&2; exit 1; }
[[ -f "$BACKUP_DIR/minio.tar.gz" ]] || { echo "minio.tar.gz não encontrado" >&2; exit 1; }
[[ -f .env ]] || { echo ".env não encontrado" >&2; exit 1; }

source .env

echo "ATENÇÃO: esta operação substituirá o banco e os objetos atuais."
[[ "${HUBFISCAL_RESTORE_CONFIRM:-}" == "RESTORE" ]] || {
  echo "Defina HUBFISCAL_RESTORE_CONFIRM=RESTORE para confirmar." >&2
  exit 1
}

docker compose stop hubfiscal-api hubfiscal-worker hubfiscal-beat
docker compose exec -T hubfiscal-postgres dropdb --if-exists -U "$POSTGRES_USER" "$POSTGRES_DB"
docker compose exec -T hubfiscal-postgres createdb -U "$POSTGRES_USER" "$POSTGRES_DB"
docker compose exec -T hubfiscal-postgres pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists < "$BACKUP_DIR/database.dump"
docker compose exec -T hubfiscal-minio sh -c 'rm -rf /data/* && tar xzf - -C /data' < "$BACKUP_DIR/minio.tar.gz"
docker compose start hubfiscal-api hubfiscal-worker hubfiscal-beat
echo "Restauração concluída."
