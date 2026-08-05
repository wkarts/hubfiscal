#!/usr/bin/env bash
set -euo pipefail
source .env
STAMP="$(date +%Y%m%d-%H%M%S)"
ROOT="${HUBFISCAL_DATA_ROOT:-./local-data}/backups/${STAMP}"
mkdir -p "$ROOT"
docker compose exec -T hubfiscal-postgres pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc > "$ROOT/database.dump"
docker compose exec -T hubfiscal-minio sh -c 'tar czf - -C /data .' > "$ROOT/minio.tar.gz"
sha256sum "$ROOT"/* > "$ROOT/SHA256SUMS"
echo "Backup criado em $ROOT"
