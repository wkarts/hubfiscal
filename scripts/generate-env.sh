#!/usr/bin/env bash
set -euo pipefail

KEEP_EXISTING=false
[[ "${1:-}" == "--keep-existing" ]] && KEEP_EXISTING=true

if [[ -f .env && "$KEEP_EXISTING" == "false" ]]; then
  echo ".env já existe. Use --keep-existing ou remova o arquivo." >&2
  exit 1
fi

if [[ ! -f .env ]]; then
  cp .env.example .env
fi

python3 - <<'PY2'
from pathlib import Path
import base64
import os
import secrets

path = Path('.env')
text = path.read_text()
values = {
    'HUBFISCAL_SECRET_KEY': secrets.token_urlsafe(64),
    'HUBFISCAL_ENCRYPTION_KEY': base64.urlsafe_b64encode(os.urandom(32)).decode(),
    'HUBFISCAL_BOOTSTRAP_TOKEN': secrets.token_urlsafe(32),
    'POSTGRES_PASSWORD': secrets.token_urlsafe(32),
    'RABBITMQ_DEFAULT_PASS': secrets.token_urlsafe(32),
    'MINIO_ROOT_PASSWORD': secrets.token_urlsafe(32),
}
for key, value in values.items():
    lines = text.splitlines()
    for idx, line in enumerate(lines):
        if line.startswith(key + '=') and ('change-me' in line or line.endswith('=')):
            lines[idx] = f'{key}={value}'
    text = '\n'.join(lines) + '\n'
# Corrige URLs derivadas
pairs = dict(line.split('=', 1) for line in text.splitlines() if '=' in line and not line.startswith('#'))
text = text.replace(
    'postgresql+asyncpg://hubfiscal:hubfiscal-change-me@hubfiscal-postgres:5432/hubfiscal',
    f"postgresql+asyncpg://hubfiscal:{pairs['POSTGRES_PASSWORD']}@hubfiscal-postgres:5432/hubfiscal",
)
text = text.replace(
    'postgresql+psycopg://hubfiscal:hubfiscal-change-me@hubfiscal-postgres:5432/hubfiscal',
    f"postgresql+psycopg://hubfiscal:{pairs['POSTGRES_PASSWORD']}@hubfiscal-postgres:5432/hubfiscal",
)
text = text.replace(
    'amqp://hubfiscal:hubfiscal-change-me@hubfiscal-rabbitmq:5672//',
    f"amqp://hubfiscal:{pairs['RABBITMQ_DEFAULT_PASS']}@hubfiscal-rabbitmq:5672//",
)
path.write_text(text)
print('Arquivo .env preparado com segredos aleatórios.')
print('HUBFISCAL_BOOTSTRAP_TOKEN:', values['HUBFISCAL_BOOTSTRAP_TOKEN'])
PY2
