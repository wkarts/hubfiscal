#!/usr/bin/env bash
set -euo pipefail
MODE="${1:-api}"

wait_db() {
  python - <<'PY2'
import asyncio
from sqlalchemy import text
from hubfiscal.core.database import engine
async def main():
    for i in range(60):
        try:
            async with engine.connect() as conn:
                await conn.execute(text('SELECT 1'))
            return
        except Exception:
            await asyncio.sleep(2)
    raise SystemExit('PostgreSQL indisponível')
asyncio.run(main())
PY2
}

wait_db
case "$MODE" in
  api)
    alembic upgrade head
    exec uvicorn hubfiscal.main:app --host 0.0.0.0 --port 8080
    ;;
  worker)
    exec celery -A hubfiscal.worker.celery_app worker --loglevel="${HUBFISCAL_LOG_LEVEL:-INFO}" --concurrency="${CELERY_CONCURRENCY:-2}"
    ;;
  beat)
    exec celery -A hubfiscal.worker.celery_app beat --loglevel="${HUBFISCAL_LOG_LEVEL:-INFO}"
    ;;
  migrate)
    exec alembic upgrade head
    ;;
  *) exec "$@" ;;
esac
