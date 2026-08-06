#!/usr/bin/env bash
set -euo pipefail

DEPLOY_DIR="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
ENV_FILE="$DEPLOY_DIR/.env"
COMPOSE_FILE="$DEPLOY_DIR/compose.yaml"
ATTEMPTS="${HUBFISCAL_HEALTH_ATTEMPTS:-30}"
INTERVAL="${HUBFISCAL_HEALTH_INTERVAL:-10}"
HEALTH_OUTPUT="${TMPDIR:-/tmp}/hubfiscal-health-${$}.json"
trap 'rm -f "$HEALTH_OUTPUT"' EXIT

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Arquivo .env ausente em $DEPLOY_DIR" >&2
  exit 1
fi
if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo "Compose ausente em $DEPLOY_DIR" >&2
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

compose() {
  docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" "$@"
}

HTTP_PORT="$(read_env WEB_PUBLISHED_PORT 2>/dev/null || true)"
HTTP_PORT="${HTTP_PORT:-58088}"
URL="http://127.0.0.1:${HTTP_PORT}/api/v1/health/live"

for ((attempt=1; attempt<=ATTEMPTS; attempt++)); do
  if curl --silent --show-error --fail --max-time 10 "$URL" > "$HEALTH_OUTPUT" 2>/dev/null; then
    api_state="$(compose ps --status running --services | grep -c '^hubfiscal-api$' || true)"
    web_state="$(compose ps --status running --services | grep -c '^hubfiscal-web$' || true)"
    worker_state="$(compose ps --status running --services | grep -c '^hubfiscal-worker$' || true)"
    beat_state="$(compose ps --status running --services | grep -c '^hubfiscal-beat$' || true)"

    if [[ "$api_state" == "1" && "$web_state" == "1" && "$worker_state" == "1" && "$beat_state" == "1" ]]; then
      echo "Health check aprovado em $URL"
      cat "$HEALTH_OUTPUT"
      echo
      compose ps
      exit 0
    fi
  fi

  echo "Aguardando Hub Fiscal: tentativa $attempt/$ATTEMPTS..."
  sleep "$INTERVAL"
done

echo "Health check não foi aprovado em $URL" >&2
compose ps -a >&2 || true
compose logs --tail=200 \
  hubfiscal-migrate hubfiscal-api hubfiscal-worker hubfiscal-beat hubfiscal-web \
  >&2 || true
exit 1
