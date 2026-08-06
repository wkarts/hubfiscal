#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE="${1:-compose.production.yaml}"
ENV_FILE="${2:-.env}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

"$SCRIPT_DIR/docker-doctor.sh" "$COMPOSE_FILE" "$ENV_FILE"

docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" pull
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d --remove-orphans

docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" ps
