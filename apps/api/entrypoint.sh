#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-api}"

wait_db() {
  python - <<'PY'
import asyncio

from sqlalchemy import text

from hubfiscal.core.database import engine


async def main() -> None:
    for attempt in range(60):
        try:
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
            return
        except Exception as exception:
            if attempt == 59:
                raise SystemExit(
                    f"PostgreSQL indisponível após 120 segundos: {exception}"
                ) from exception
            await asyncio.sleep(2)


asyncio.run(main())
PY
}

case "$MODE" in
  api)
    wait_db
    if [[ "${HUBFISCAL_AUTO_MIGRATE:-false}" == "true" ]]; then
      alembic upgrade head
    fi
    exec uvicorn hubfiscal.main:app \
      --host 0.0.0.0 \
      --port 8080 \
      --proxy-headers \
      --forwarded-allow-ips="${HUBFISCAL_FORWARDED_ALLOW_IPS:-*}"
    ;;
  worker)
    wait_db
    exec celery -A hubfiscal.worker.celery_app worker \
      --loglevel="${HUBFISCAL_LOG_LEVEL:-INFO}" \
      --concurrency="${CELERY_CONCURRENCY:-2}" \
      --without-mingle \
      --without-gossip
    ;;
  beat)
    wait_db
    exec celery -A hubfiscal.worker.celery_app beat \
      --loglevel="${HUBFISCAL_LOG_LEVEL:-INFO}" \
      --schedule=/tmp/celery/celerybeat-schedule
    ;;
  migrate)
    wait_db
    exec alembic upgrade head
    ;;
  *)
    exec "$@"
    ;;
esac
