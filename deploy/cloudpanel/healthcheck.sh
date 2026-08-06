#!/usr/bin/env bash
set -euo pipefail

DEPLOY_DIR="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
ENV_FILE="$DEPLOY_DIR/.env"
COMPOSE_FILE="$DEPLOY_DIR/compose.yaml"
ATTEMPTS="${HUBFISCAL_HEALTH_ATTEMPTS:-30}"
INTERVAL="${HUBFISCAL_HEALTH_INTERVAL:-10}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Arquivo .env ausente em $DEPLOY_DIR" >&2
  exit 1
fi

HTTP_PORT="$(sed -n 's/^HUBFISCAL_HTTP_PORT=//p' "$ENV_FILE" | tail -n1)"
HTTP_PORT="${HTTP_PORT:-8088}"
URL="http://127.0.0.1:${HTTP_PORT}/api/v1/health/live"

for ((attempt=1; attempt<=ATTEMPTS; attempt++)); do
  if curl --silent --show-error --fail --max-time 10 "$URL" >/tmp/hubfiscal-health.json 2>/dev/null; then
    echo "Health check aprovado em $URL"
    cat /tmp/hubfiscal-health.json
    echo
    docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" ps
    exit 0
  fi
  echo "Aguardando Hub Fiscal: tentativa $attempt/$ATTEMPTS..."
  sleep "$INTERVAL"
done

echo "Health check não respondeu em $URL" >&2
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" ps >&2 || true
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" logs --tail=150 hubfiscal-api hubfiscal-web >&2 || true
exit 1
