#!/usr/bin/env bash
set -euo pipefail

KEEP_EXISTING=false
POSITIONAL=()

for argument in "$@"; do
  case "$argument" in
    --keep-existing)
      KEEP_EXISTING=true
      ;;
    -h|--help)
      cat <<'EOF'
Uso:
  generate-env.sh [--keep-existing]
  generate-env.sh TEMPLATE OUTPUT [--keep-existing]

Exemplos:
  bash scripts/generate-env.sh
  bash scripts/generate-env.sh --keep-existing
  bash scripts/generate-env.sh deploy/cloudpanel/.env.example /tmp/hubfiscal/.env
EOF
      exit 0
      ;;
    *)
      POSITIONAL+=("$argument")
      ;;
  esac
done

if (( ${#POSITIONAL[@]} > 2 )); then
  echo "Número inválido de argumentos. Use --help." >&2
  exit 1
fi

TEMPLATE="${POSITIONAL[0]:-.env.example}"
OUTPUT="${POSITIONAL[1]:-.env}"

if [[ ! -f "$TEMPLATE" ]]; then
  echo "Template não encontrado: $TEMPLATE" >&2
  exit 1
fi

if [[ -f "$OUTPUT" && "$KEEP_EXISTING" == "false" ]]; then
  echo "$OUTPUT já existe. Use --keep-existing ou remova o arquivo." >&2
  exit 1
fi

if [[ ! -f "$OUTPUT" ]]; then
  install -m 600 "$TEMPLATE" "$OUTPUT"
fi

ENV_OUTPUT="$OUTPUT" python3 - <<'PY'
from __future__ import annotations

import base64
import os
import secrets
from pathlib import Path

path = Path(os.environ["ENV_OUTPUT"])
lines = path.read_text(encoding="utf-8").splitlines()

values = {
    "HUBFISCAL_SECRET_KEY": secrets.token_urlsafe(64),
    "HUBFISCAL_ENCRYPTION_KEY": base64.urlsafe_b64encode(
        os.urandom(32)
    ).decode(),
    "HUBFISCAL_BOOTSTRAP_TOKEN": secrets.token_urlsafe(32),
    "POSTGRES_PASSWORD": secrets.token_urlsafe(32),
    "RABBITMQ_PASSWORD": secrets.token_urlsafe(32),
    "MINIO_PASSWORD": secrets.token_urlsafe(32),
}

changed: set[str] = set()
for index, line in enumerate(lines):
    if not line or line.lstrip().startswith("#") or "=" not in line:
        continue
    key, current = line.split("=", 1)
    if key in values and (
        not current
        or "change-me" in current
        or current.startswith("replace-")
    ):
        lines[index] = f"{key}={values[key]}"
        changed.add(key)

path.write_text("\n".join(lines) + "\n", encoding="utf-8")
path.chmod(0o600)

print(f"Ambiente preparado: {path}")
if "HUBFISCAL_BOOTSTRAP_TOKEN" in changed:
    print("HUBFISCAL_BOOTSTRAP_TOKEN:", values["HUBFISCAL_BOOTSTRAP_TOKEN"])
PY
